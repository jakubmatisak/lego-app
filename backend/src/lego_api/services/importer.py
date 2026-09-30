"""Hromadný import: koncept, dohľadanie setov, náhľad, zápis a vrátenie.

Poradie je zámerne opatrné. Súbor sa najprv len rozoberie a uloží ako
koncept, neznáme čísla sa dohľadajú na pozadí a používateľ vidí pri každom
riadku, čo z neho vznikne. Kusy vzniknú až po potvrdení, v jednej
transakcii, a každý nesie ``import_batch_id``, takže sa import dá celý
vrátiť bez toho, aby sa dotkol ručne pridaných vecí.

Import sa nepýta na ceny (BrickEconomy) ani na Brickset: 300 nových setov
by minulo ich denný limit na tri dni. Metadáta sú len z Rebrickable, ktorý
denný limit nemá, sekundu od seba. Popis a štítky doplní neskôr bežné
dopĺňanie z Brickset, ceny tlačidlo obnovy.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api import api_log
from lego_api.config import Settings
from lego_api.models import (
    CatalogItem,
    CollectionItem,
    ImportBatch,
    ImportState,
    ItemCondition,
    ItemPhoto,
    ItemPurpose,
    ItemStatus,
    WishlistItem,
)
from lego_api.models.base import utcnow
from lego_api.providers.brickset import BricksetProvider
from lego_api.services.catalog import CatalogService
from lego_api.services.import_file import OWNED, SOLD, WISH, ParsedFile
from lego_api.services.keys import UserKeys
from lego_api.services.wishlist import added_at, drop_bought

log = logging.getLogger(__name__)

#: Rebrickable znesie zhruba jedno volanie za sekundu.
LOOKUP_PAUSE_SECONDS = 1.0
#: Nepotvrdený koncept sa po dni zmaže.
DRAFT_TTL = timedelta(hours=24)

OK, DUPLICATE, ERROR = "ok", "duplicate", "error"

#: Importy, ktorých dohľadanie práve beží v tomto procese.
_running: set[int] = set()


def _catalog(session: AsyncSession, settings: Settings, keys: UserKeys) -> CatalogService:
    """Katalóg bez Brickset: jeho getSets by pri stovkách setov minul denný limit."""
    return CatalogService(session, settings, keys, brickset=BricksetProvider(settings, None))


# --- koncept ------------------------------------------------------------------------


async def create_batch(
    session: AsyncSession,
    settings: Settings,
    keys: UserKeys,
    user_id: int,
    filename: str,
    parsed: ParsedFile,
) -> ImportBatch:
    """Uloží rozobraté riadky a priradí im to, čo katalóg už pozná."""
    await prune_drafts(session, user_id)
    service = _catalog(session, settings, keys)
    rows: list[dict] = []
    pending: set[str] = set()
    for parsed_row in parsed.rows:
        row = {
            "line": parsed_row.line,
            **parsed_row.values,
            "errors": list(parsed_row.errors),
            "warnings": list(parsed_row.warnings),
            "catalog_num": None,
            "name": None,
            "image_url": None,
            "unidentified": False,
            "state": ERROR if parsed_row.errors else OK,
            "pending": False,
        }
        num = row["raw_num"]
        if num:
            found = await service.get_local(num)
            if found is not None:
                _attach(row, found)
            else:
                row["pending"] = True
                pending.add(num)
        rows.append(row)

    batch = ImportBatch(
        user_id=user_id,
        filename=filename[:200] or "import",
        rows=rows,
        ignored_columns=parsed.ignored_columns,
        progress_total=len(pending),
        state=ImportState.LOOKING_UP if pending else ImportState.READY,
    )
    if pending and not keys.rebrickable:
        # Bez kľúča sa nedá nič dohľadať, nemá zmysel čakať.
        for row in rows:
            if row["pending"]:
                row["pending"] = False
                row["errors"].append(
                    "Set nie je v katalógu appky. Na dohľadanie treba kľúč Rebrickable "
                    "(Nastavenia → Dáta)."
                )
        batch.progress_total = 0
        batch.state = ImportState.READY
    if batch.state == ImportState.READY:
        await classify(session, user_id, batch)
    session.add(batch)
    await session.commit()
    return batch


def _attach(row: dict, catalog: CatalogItem) -> None:
    row["catalog_num"] = catalog.catalog_num
    row["name"] = catalog.name
    row["image_url"] = catalog.image_url
    row["pending"] = False
    if catalog.is_series and row["ownership"] != WISH:
        # Z čísla na sáčku sa nedá povedať, ktorá figúrka je vnútri.
        row["unidentified"] = True
        row["warnings"].append(
            "Číslo celej série: importuje sa ako nerozbalený sáčok, figúrku doplníš "
            "v detaile po rozbalení. Konkrétna figúrka má číslo s pomlčkou, napr. "
            f"{catalog.catalog_num}-3."
        )


async def look_up(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    keys: UserKeys,
    batch_id: int,
    pause: float | None = None,
) -> None:
    """Na pozadí dohľadá čísla, ktoré katalóg nepoznal, a potom riadky zatriedi."""
    if batch_id in _running:
        return
    _running.add(batch_id)
    delay = LOOKUP_PAUSE_SECONDS if pause is None else pause
    try:
        async with sessionmaker() as session:
            batch = await session.get(ImportBatch, batch_id)
            if batch is None or batch.state != ImportState.LOOKING_UP:
                return
            api_log.set_user(batch.user_id)
            service = _catalog(session, settings, keys)
            rows = [dict(r) for r in batch.rows]
            nums = sorted({r["raw_num"] for r in rows if r.get("pending")})
            found: dict[str, CatalogItem | None] = {}
            for index, num in enumerate(nums):
                if index > 0 and delay > 0:
                    await asyncio.sleep(delay)
                try:
                    found[num] = await service.resolve(num)
                    await session.commit()
                except Exception as exc:  # jeden zlý set nesmie zastaviť celý import
                    log.warning("Import: set %s sa nepodarilo dohľadať: %s", num, exc)
                    await session.rollback()
                    found[num] = None
                batch = await session.get(ImportBatch, batch_id)
                if batch is None:
                    return
                batch.progress_done = index + 1
                await session.commit()

            for row in rows:
                if not row.get("pending"):
                    continue
                catalog = found.get(row["raw_num"])
                if catalog is None:
                    row["pending"] = False
                    row["errors"].append(
                        f"Číslo {row['raw_num']} sa nenašlo ani v Rebrickable. Skontroluj ho; "
                        "set, ktorý v žiadnom katalógu nie je, pridáš ručne cez Pridať set."
                    )
                else:
                    _attach(row, catalog)
            batch.rows = rows
            batch.state = ImportState.READY
            await classify(session, batch.user_id, batch)
            await session.commit()
    finally:
        _running.discard(batch_id)


def needs_restart(batch: ImportBatch) -> bool:
    """Dohľadanie ostalo stáť (napríklad reštart servera uprostred)."""
    return batch.state == ImportState.LOOKING_UP and batch.id not in _running


# --- zatriedenie riadkov ---------------------------------------------------------


def _money(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


async def classify(session: AsyncSession, user_id: int, batch: ImportBatch) -> None:
    """Stav každého riadku: ok, duplicita alebo chyba, s upozorneniami navyše.

    Duplicita vlastneného kusu je rovnaký set s rovnakým dátumom a cenou
    kúpy (aj keď sa medzitým predal), predaného rovnaký dátum a cena predaja.
    Opätovné nahratie toho istého súboru tak nič nezdvojí.
    """
    items = list(
        (await session.execute(select(CollectionItem).where(CollectionItem.user_id == user_id)))
        .scalars()
        .all()
    )
    wishes = {
        w.catalog_num
        for w in (
            await session.execute(select(WishlistItem).where(WishlistItem.user_id == user_id))
        ).scalars()
    }
    owned_nums = {i.catalog_num for i in items if i.status != ItemStatus.SOLD}
    wished_in_file: set[str] = set()

    rows = []
    for original in batch.rows:
        row = dict(original)
        # Výsledok porovnania so zbierkou sa pri každom zatriedení počíta znova,
        # chyby a upozornenia zo súboru ostávajú.
        checks: list[str] = []
        problems: list[str] = []
        row["duplicate_of"] = 0
        num = row.get("catalog_num")
        if num is None and not row["errors"]:
            problems.append("Set sa nenašiel.")
        if num is not None and not row["errors"]:
            if row["ownership"] == WISH:
                if num in wishes:
                    row["duplicate_of"] = 1
                    checks.append("Tento set už v Chcem je.")
                elif num in wished_in_file:
                    problems.append("Ten istý set je v Chcem už vyššie v súbore.")
                if num in owned_nums:
                    checks.append("Tento set už v zbierke máš.")
                wished_in_file.add(num)
            else:
                if row["ownership"] == SOLD:
                    same = [
                        i
                        for i in items
                        if i.catalog_num == num
                        and i.status == ItemStatus.SOLD
                        and i.sold_date == _day(row["sold_date"])
                        and i.sold_price_eur == _money(row["sold_price"])
                    ]
                else:
                    same = [
                        i
                        for i in items
                        if i.catalog_num == num
                        and i.purchase_date == _day(row["purchase_date"])
                        and i.purchase_price_eur == _money(row["purchase_price"])
                    ]
                if same:
                    row["duplicate_of"] = len(same)
                    checks.append(
                        f"V zbierke už {_pieces(len(same))} s rovnakým dátumom a cenou. "
                        "Preskočí sa, ak ho nezaškrtneš."
                    )
                if num in wishes and row["ownership"] == OWNED:
                    checks.append("Je v Chcem, po importe sa odtiaľ vyradí.")
        row["check_warnings"] = checks
        row["check_errors"] = problems
        if row["errors"] or problems:
            row["state"] = ERROR
        elif row["duplicate_of"]:
            row["state"] = DUPLICATE
        else:
            row["state"] = OK
        rows.append(row)
    batch.rows = rows


def _pieces(count: int) -> str:
    if count == 1:
        return "je 1 taký kus"
    if 2 <= count <= 4:
        return f"sú {count} také kusy"
    return f"je {count} takých kusov"


# --- zápis a vrátenie ---------------------------------------------------------------


class ImportNotReady(ValueError):
    pass


async def commit(
    session: AsyncSession, user_id: int, batch: ImportBatch, include_duplicates: set[int]
) -> ImportBatch:
    """Vytvorí kusy a položky Chcem. Riadky s chybou sa preskočia."""
    if batch.state != ImportState.READY:
        raise ImportNotReady(
            "Import už prebehol." if batch.state != ImportState.LOOKING_UP else "Ešte sa dohľadáva."
        )
    await classify(session, user_id, batch)

    pieces: list[CollectionItem] = []
    wishes_created = 0
    for row in batch.rows:
        wanted = row["state"] == OK or (
            row["state"] == DUPLICATE
            and row["ownership"] != WISH
            and row["line"] in include_duplicates
        )
        if not wanted:
            continue
        if row["ownership"] == WISH:
            session.add(
                WishlistItem(
                    user_id=user_id,
                    catalog_num=row["catalog_num"],
                    target_price_eur=_money(row["target_price"]),
                    note=row["note"],
                    import_batch_id=batch.id,
                )
            )
            wishes_created += 1
            continue
        sold = row["ownership"] == SOLD
        for _ in range(row["quantity"]):
            pieces.append(
                CollectionItem(
                    user_id=user_id,
                    catalog_num=row["catalog_num"],
                    status=ItemStatus.SOLD if sold else ItemStatus.OWNED,
                    condition=ItemCondition(row["condition"]),
                    unidentified=row["unidentified"],
                    flags=row["flags"],
                    purchase_price_eur=_money(row["purchase_price"]),
                    purchase_date=_day(row["purchase_date"]),
                    purchase_place=row["purchase_place"],
                    location=row["location"],
                    box=row.get("box"),
                    purpose=ItemPurpose(row["purpose"]) if row["purpose"] else None,
                    note=row["note"],
                    sold_price_eur=_money(row["sold_price"]) if sold else None,
                    sold_date=_day(row["sold_date"]) if sold else None,
                    sold_via=row["sold_via"] if sold else None,
                    sold_fees_eur=_money(row["sold_fees"]) if sold else None,
                    sold_shipping_eur=_money(row["sold_shipping"]) if sold else None,
                    import_batch_id=batch.id,
                )
            )
    session.add_all(pieces)

    # Kúpené sa vyradí z Chcem, ako pri každom pridaní kusu. Vrátenie ho obnoví.
    dropped = await drop_bought(session, user_id, pieces, keep_imported=True)

    batch.removed_wishes = [wish.as_json() for wish in dropped.values()]
    batch.pieces_created = len(pieces)
    batch.wishes_created = wishes_created
    batch.state = ImportState.COMMITTED
    batch.committed_at = utcnow()
    await session.commit()
    return batch


async def undo(
    session: AsyncSession, settings: Settings, user_id: int, batch: ImportBatch
) -> ImportBatch:
    """Zmaže všetko, čo import vytvoril, aj s fotkami, a vráti vyradené z Chcem."""
    if batch.state != ImportState.COMMITTED:
        raise ImportNotReady("Vrátiť sa dá len dokončený import.")
    items = list(
        (
            await session.execute(
                select(CollectionItem).where(
                    CollectionItem.user_id == user_id, CollectionItem.import_batch_id == batch.id
                )
            )
        ).scalars()
    )
    if items:
        photos = (
            await session.execute(
                select(ItemPhoto).where(ItemPhoto.item_id.in_([i.id for i in items]))
            )
        ).scalars()
        for photo in photos:
            (Path(settings.photos_dir) / photo.filename).unlink(missing_ok=True)
            await session.delete(photo)
    for item in items:
        await session.delete(item)
    await session.execute(
        delete(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.import_batch_id == batch.id
        )
    )
    await session.flush()

    existing = {
        w.catalog_num
        for w in (
            await session.execute(select(WishlistItem).where(WishlistItem.user_id == user_id))
        ).scalars()
    }
    for wish in batch.removed_wishes or []:
        if wish["catalog_num"] in existing:
            continue
        if await session.get(CatalogItem, wish["catalog_num"]) is None:
            continue
        restored = WishlistItem(
            user_id=user_id,
            catalog_num=wish["catalog_num"],
            target_price_eur=_money(wish.get("target_price_eur")),
            note=wish.get("note"),
        )
        if wish.get("created_at"):
            restored.created_at = added_at(datetime.fromisoformat(wish["created_at"]))
        session.add(restored)
    batch.state = ImportState.UNDONE
    batch.undone_at = utcnow()
    await session.commit()
    return batch


async def prune_drafts(session: AsyncSession, user_id: int) -> None:
    """Nepotvrdené koncepty staršie ako deň sa zmažú."""
    await session.execute(
        delete(ImportBatch).where(
            ImportBatch.user_id == user_id,
            ImportBatch.state.in_([ImportState.READY, ImportState.LOOKING_UP]),
            ImportBatch.created_at < utcnow() - DRAFT_TTL,
        )
    )


def counts(batch: ImportBatch) -> dict:
    """Súhrn pre hlavičku náhľadu a pre históriu."""
    rows = batch.rows or []
    ok = [r for r in rows if r["state"] == OK]
    return {
        "rows": len(rows),
        "ok": len(ok),
        "duplicate": sum(1 for r in rows if r["state"] == DUPLICATE),
        "error": sum(1 for r in rows if r["state"] == ERROR),
        "pieces": sum(r["quantity"] for r in ok if r["ownership"] == OWNED),
        "sold": sum(r["quantity"] for r in ok if r["ownership"] == SOLD),
        "wishes": sum(1 for r in ok if r["ownership"] == WISH),
    }
