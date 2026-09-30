"""Záloha databázy pri aktualizácii appky.

Pri prvom štarte novej verzie appky Alembic databázu sám zmigruje
(``main.py::_migrate``). Predtým vznikne kópia v priečinku ``backups``
vedľa databázy, keď:

- migrácia niečo zmení (revízia v ``alembic_version`` nie je head), alebo
- nad databázou naposledy bežala iná verzia appky, novšia aj staršia, hoci
  sa schéma nemení. Verziu si appka po úspešnom štarte zapíše do
  ``app_settings`` pod kľúč ``app_version`` (``VERSION_KEY``).

Meno zálohy je ``lego-RRRRMMDD-HHMMSS-v<verzia>-<revízia>.db``, teda
verzia a revízia, s ktorými databáza do štartu bola. Databáza spred
zapisovania verzie (staršie inštalácie, revízie ešte bez ``app_settings``)
verziu nemá, zálohuje sa ako prvý štart novej verzie a v mene je len
revízia. Keby niečo spadlo alebo pokazilo údaje, stačí appku zastaviť
a spustiť ``python -m lego_api.cli restore-backup <záloha>``
(``restore_backup``): doterajšiu databázu aj so zvyškami žurnálu
(``lego.db-journal``, ``-wal``, ``-shm``) odloží do ``backups`` a zálohu
skopíruje na jej miesto. Ručne treba žurnál zmazať a zálohu skopírovať späť.

Kópia ide cez zálohovacie API SQLite, takže je konzistentná aj pri
otvorenom spojení. Nová alebo prázdna databáza (bez ``alembic_version``)
a databáza v pamäti sa nezálohujú, nie je čo stratiť; verzia sa do nich
po štarte len zapíše. Keď sa záloha nepodarí (plný disk, práva), migrácia
sa nespustí: bez zálohy dáta nemeníme.

Až po úspešnej migrácii sa zapíše verzia a ostane posledných ``KEEP``
záloh, žiadna staršia než ``MAX_AGE_DAYS`` dní; iné súbory v priečinku
ostanú. Vek sa stráži pri každom úspešnom štarte, aj bez novej zálohy:
zálohy nesú aj údaje zmazaných účtov a nemajú ostať natrvalo, keď nová
verzia dlho nevyjde. Pred migráciou sa nemaže nič: keď
štart padá a appka sa spúšťa znova (Docker ``restart``, ďalšie spustenie
desktopu), rotácia by inak vytlačila jedinú zálohu spred aktualizácie
kópiami napoly zmigrovanej databázy. Zlyhanie si pamätá značka
(``failure_marker``) s odtlačkom databázy; kým sa databáza odvtedy
nezmenila, ďalší pokus novú zálohu nerobí a hlási tú pôvodnú. Každý
úspešný štart značku zmaže, aj ten, ktorý nič nezálohoval (návrat zálohy
a predchádzajúcej verzie).
"""

import json
import logging
import os
import re
import shutil
import sqlite3
import time
from collections.abc import Callable, Collection
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

import lego_api

log = logging.getLogger(__name__)

#: Koľko posledných záloh ostane. Aktualizácia býva raz za čas.
KEEP = 5
#: Zálohu staršiu než toľko dní zmaže každý úspešný štart. Nesú aj údaje
#: neskôr zmazaných účtov (zásady /sukromie, Ako dlho).
MAX_AGE_DAYS = 90
#: Zvyšky žurnálu SQLite vedľa databázy: ``lego.db-journal`` a spol.
SIDECARS = ("journal", "wal", "shm")
#: Časť mena databázy odloženej pri návrate zálohy (``restore_backup``).
ASIDE_LABEL = "pred-obnovou"
FOLDER = "backups"
_STAMP = "%Y%m%d-%H%M%S"
#: Kľúč v ``app_settings``: verzia appky, ktorá nad databázou naposledy nabehla.
VERSION_KEY = "app_version"


class BackupFailed(RuntimeError):
    """Záloha pred aktualizáciou sa nepodarila, preto sa migrácia nespustila."""


@dataclass(frozen=True)
class Pending:
    """Databáza pred štartom, ktorú treba zálohovať: jej revízia a posledná verzia."""

    revision: str
    #: Verzia appky, ktorá nad ňou naposledy bežala; None = nezapísaná.
    version: str | None

    @property
    def label(self) -> str:
        """Časť mena zálohy: ``v<verzia>-<revízia>``, bez známej verzie len revízia."""
        revision = _safe(self.revision)
        return f"v{_safe(self.version)}-{revision}" if self.version else revision


def _safe(text: str) -> str:
    """Do mena súboru len písmená, číslice a bodky; zvyšok (aj oddeľovač cesty) je ``_``."""
    return re.sub(r"[^0-9A-Za-z.]+", "_", text)


def _app_version() -> str:
    # Pri volaní, nie pri importe: testy si verziu podhodia.
    return lego_api.__version__


def sqlite_path(database_url: str) -> Path | None:
    """Súbor databázy z ``DATABASE_URL``; None pre pamäť alebo iný databázový stroj."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    if url.query.get("mode") == "memory":
        return None
    database = (url.database or "").removeprefix("file:")
    if not database or database == ":memory:":
        return None
    return Path(database)


def current_revisions(db_path: Path) -> set[str]:
    """Revízie zapísané v ``alembic_version``; prázdna množina = nová databáza."""
    with closing(sqlite3.connect(db_path)) as conn:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
        if table is None:
            return set()
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    return {row[0] for row in rows if row[0]}


def head_revisions(config: Config) -> set[str]:
    """Posledné revízie zo skriptov Alembicu, teda kam ide ``upgrade head``."""
    return set(ScriptDirectory.from_config(config).get_heads())


def recorded_version(db_path: Path) -> str | None:
    """Verzia appky zapísaná v databáze; None = nezapísaná alebo nečitateľná.

    Číta sa pred migráciou, teda v schéme hocijakej staršej revízie, preto
    surové SQL a žiadna výnimka. Chýbajúca tabuľka (revízia spred nej) aj
    nečakaná hodnota znamenajú „nevieme“, a to sa zálohuje.
    """
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            return _version_of(conn)
    except sqlite3.Error:
        return None


def _version_of(conn: sqlite3.Connection) -> str | None:
    """Verzia z ``app_settings`` otvorenej databázy; None = nezapísaná či nečitateľná."""
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (VERSION_KEY,)
        ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    try:
        value = json.loads(row[0])
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, str) and value else None


def record_version(db_path: Path, version: str) -> None:
    """Po úspešnej migrácii zapíše, s akou verziou appka nad databázou beží.

    Tú istú verziu neprepisuje, zbytočný zápis by zmenil odtlačok databázy.
    Schéma je už head, surové SQL stačí; hodnota je JSON a čas v tvare, ktorý
    zapisuje SQLAlchemy, aby riadok appka prečítala ako každé iné nastavenie.
    Keď zápis zlyhá, appka aj tak nabehne, ďalší štart len zálohuje znova.
    """
    if recorded_version(db_path) == version:
        return
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (VERSION_KEY, json.dumps(version), stamp),
            )
            conn.commit()
    except sqlite3.Error as exc:
        log.warning(
            "Verziu appky %s sa do databázy %s nepodarilo zapísať: %s. "
            "Ďalší štart databázu zálohuje znova.",
            version,
            db_path,
            exc,
        )


def pending_backup(db_path: Path | None, heads: set[str], version: str) -> Pending | None:
    """Čo zálohovať pred štartom verzie ``version``; None, keď netreba.

    Zálohuje sa, keď migrácia databázu zmení, alebo keď nad ňou naposledy
    bežala iná verzia appky, aj nezapísaná (databáza spred tejto evidencie).
    Nová alebo prázdna databáza nemá čo stratiť.
    """
    if db_path is None or not db_path.is_file():
        return None
    current = current_revisions(db_path)
    if not current:
        return None
    last = recorded_version(db_path)
    if current == heads and last == version:
        return None
    return Pending("_".join(sorted(current)), last)


def failure_marker(db_path: Path) -> Path:
    """Značka v ``backups``: štart po tejto zálohe zlyhal (JSON so zálohou a odtlačkom).

    Meno ostáva z čias, keď sa zálohovalo len pred migráciou, aby platila
    aj značka, ktorú nechala staršia verzia.
    """
    return db_path.parent / FOLDER / f"{db_path.stem}-failed-migration.json"


def _fingerprint(db_path: Path) -> dict[str, int]:
    """Odtlačok databázy: veľkosť, čas zmeny a počítadlo zmien z hlavičky SQLite.

    Počítadlo (bajty 24 až 27) SQLite zvýši pri každom potvrdenom zápise,
    takže zmenu odhalí aj vtedy, keď čas súboru ostal rovnaký.
    """
    stat = db_path.stat()
    with db_path.open("rb") as handle:
        header = handle.read(28)
    counter = int.from_bytes(header[24:28], "big") if len(header) == 28 else -1
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "counter": counter}


def _earlier_backup(db_path: Path, revision: str) -> Path | None:
    """Záloha spred zlyhaného štartu, ktorá platí aj teraz; inak None.

    Platí, keď databáza stojí na tej istej revízii, záloha existuje a databáza
    je presne taká, ako ju zlyhaný pokus nechal. Keď ju medzitým niekto zmenil
    (vrátil zálohu a pracoval v starej verzii), treba zálohovať znova.
    """
    marker = failure_marker(db_path)
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        saved = marker.parent / str(data["backup"])
        if data["revision"] != revision or data["fingerprint"] != _fingerprint(db_path):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if saved.parent != marker.parent or not _pattern(db_path.stem).match(saved.name):
        return None
    return saved if saved.is_file() else None


def _remember_failure(db_path: Path, saved: Path) -> None:
    """Zapíše značku po zlyhanej migrácii; bez nej by ďalší štart zálohoval znova.

    Revízia je tá, na ktorej databáza ostala, nie tá v mene zálohy: SQLite
    potvrdzuje každú migráciu zvlášť, takže prvá mohla prejsť a spadla až ďalšia.
    """
    try:
        revision = "_".join(sorted(current_revisions(db_path)))
        failure_marker(db_path).write_text(
            json.dumps(
                {
                    "backup": saved.name,
                    "revision": revision,
                    "fingerprint": _fingerprint(db_path),
                }
            ),
            encoding="utf-8",
        )
    except (OSError, sqlite3.Error) as exc:
        log.warning("Značku o zlyhanej migrácii sa nepodarilo zapísať: %s", exc)


def _forget_failure(db_path: Path) -> None:
    with suppress(OSError):
        failure_marker(db_path).unlink(missing_ok=True)


def _marked_backup(db_path: Path) -> Path | None:
    """Záloha, na ktorú ukazuje značka o zlyhaní, kým značka je (napr. nešla zmazať)."""
    marker = failure_marker(db_path)
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return marker.parent / Path(str(data["backup"])).name
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _pattern(stem: str) -> re.Pattern[str]:
    """Mená záloh tejto databázy, s verziou v mene aj staršie bez nej."""
    return re.compile(rf"^{re.escape(stem)}-\d{{8}}-\d{{6}}-[0-9A-Za-z_.-]+\.db$")


def _copy(source: sqlite3.Connection, target: sqlite3.Connection) -> None:
    """Konzistentná kópia aj pri otvorenom spojení appky."""
    source.backup(target)


def backup(db_path: Path, label: str, *, now: datetime | None = None) -> Path:
    """Skopíruje databázu do ``backups``. Staré zálohy nemaže, to robí ``prune``."""
    folder = db_path.parent / FOLDER
    stamp = (now or datetime.now()).strftime(_STAMP)
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", label)
    target = folder / f"{db_path.stem}-{stamp}-{safe}.db"
    # Rozpísaná kópia (plný disk) nesmie vyzerať ako platná záloha
    # ani vytlačiť staršiu dobrú, preto sa premenuje až hotová.
    partial = target.with_name(target.name + ".part")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(partial)) as copy:
            _copy(source, copy)
        os.replace(partial, target)
    except (OSError, sqlite3.Error) as exc:
        with suppress(OSError):
            partial.unlink(missing_ok=True)
        raise BackupFailed(
            f"Záloha databázy {db_path} pred aktualizáciou zlyhala: {exc}. "
            "Migrácia sa nespustila, databáza ostala bez zmeny. "
            f"Skontroluj voľné miesto na disku a práva k priečinku {folder}."
        ) from exc
    return target


def _with_sidecars(path: Path) -> list[Path]:
    """Súbor databázy a mená jeho žurnálu, v tomto poradí."""
    return [path, *(path.with_name(f"{path.name}-{suffix}") for suffix in SIDECARS)]


def prune(
    folder: Path,
    stem: str,
    keep: int = KEEP,
    *,
    max_age_days: int = MAX_AGE_DAYS,
    now: datetime | None = None,
    protect: Collection[Path] = (),
) -> list[Path]:
    """Zmaže zálohy tejto databázy nad ``keep`` a staršie než ``max_age_days`` dní.

    Vek je čas v mene zálohy, nie čas súboru, ktorý kópia zmení. Zálohy
    v ``protect`` ostanú vždy. So zálohou zmizne aj jej žurnál (``-journal``,
    ``-wal``, ``-shm``; má ho len databáza odložená pri návrate zálohy).
    Cudzie súbory ostanú.
    """
    pattern = _pattern(stem)
    try:
        # V mene je čas s pevnou šírkou hneď za menom databázy,
        # takže abecedne = chronologicky, s verziou v mene aj bez nej.
        ours = sorted(
            (p for p in folder.iterdir() if p.is_file() and pattern.match(p.name)),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError as exc:
        if folder.exists():
            log.warning("Priečinok záloh %s sa nepodarilo prečítať: %s", folder, exc)
        return []
    kept = {p.name for p in protect}
    cutoff = ((now or datetime.now()) - timedelta(days=max_age_days)).strftime(_STAMP)
    start = len(stem) + 1
    removed: list[Path] = []
    for index, old in enumerate(ours):
        too_old = old.name[start : start + len(cutoff)] < cutoff
        if old.name in kept or (index < keep and not too_old):
            continue
        try:
            old.unlink()
        except OSError as exc:
            log.warning("Starú zálohu %s sa nepodarilo zmazať: %s", old, exc)
            continue
        removed.append(old)
        for leftover in _with_sidecars(old)[1:]:
            with suppress(OSError):
                leftover.unlink(missing_ok=True)
    if removed:
        log.info(
            "Zmazané staré zálohy (ostáva najviac %s, žiadna staršia než %s dní): %s",
            keep,
            max_age_days,
            ", ".join(p.name for p in removed),
        )
    return removed


def _reason(pending: Pending, heads: set[str], version: str) -> str:
    if pending.revision != "_".join(sorted(heads)):
        return (
            f"Migrácia zmení databázu (revízia {pending.revision} na "
            f"{', '.join(sorted(heads))}), najprv záloha."
        )
    if pending.version is None:
        return (
            f"Prvý štart verzie {version} nad touto databázou, predchádzajúca verzia "
            "nie je zapísaná. Najprv záloha."
        )
    return f"Nová verzia appky {version} (predtým {pending.version}), najprv záloha databázy."


def backup_before_upgrade(
    database_url: str,
    config: Config,
    *,
    version: str | None = None,
    now: datetime | None = None,
) -> Path | None:
    """Záloha pred štartom, keď migrácia niečo zmení alebo sa zmenila verzia; inak None.

    ``version`` je verzia, ktorá sa spúšťa (predvolene táto appka). Po
    zlyhanom štarte, keď sa databáza odvtedy nezmenila, vráti zálohu spred
    neho a novú nerobí (``_earlier_backup``).
    """
    db_path = sqlite_path(database_url)
    heads = head_revisions(config)
    version = version or _app_version()
    try:
        pending = pending_backup(db_path, heads, version)
    except sqlite3.Error as exc:
        raise BackupFailed(
            f"Revíziu databázy {db_path} sa nepodarilo prečítať: {exc}. "
            "Migrácia sa nespustila, databáza ostala bez zmeny."
        ) from exc
    if pending is None or db_path is None:
        return None
    earlier = _earlier_backup(db_path, pending.revision)
    if earlier is not None:
        log.warning(
            "Predchádzajúci štart (revízia %s) zlyhal a databáza sa odvtedy nezmenila. "
            "Nová záloha sa nerobí, stav spred aktualizácie je v %s.",
            pending.revision,
            earlier,
        )
        return earlier
    log.info(_reason(pending, heads, version))
    saved = backup(db_path, pending.label, now=now)
    log.info("Záloha databázy pred aktualizáciou: %s", saved)
    return saved


def upgrade_with_backup(
    database_url: str,
    config: Config,
    upgrade: Callable[[], object],
    *,
    version: str | None = None,
) -> Path | None:
    """Zálohuje a potom migruje. Bez zálohy sa ``upgrade`` nezavolá.

    Keď migrácia spadne, zapíše značku, zaloguje, kde je záloha a ako ju
    vrátiť, a výnimku nechá ísť ďalej; verzia ostane stará. Po úspechu
    zapíše verziu, zmaže značku a staré zálohy.
    """
    version = version or _app_version()
    saved = backup_before_upgrade(database_url, config, version=version)
    db_path = sqlite_path(database_url)
    try:
        upgrade()
    except Exception as exc:
        if saved is not None and db_path is not None:
            _remember_failure(db_path, saved)
            restore = f"python -m lego_api.cli restore-backup {saved}"
            leftovers = ", ".join(p.name for p in _with_sidecars(db_path)[1:])
            log.error(
                "Migrácia databázy zlyhala (%s). Stav pred aktualizáciou je v zálohe %s. "
                "Na návrat zastav appku a spusti %s (v Dockeri docker compose run --rm app "
                "%s), potom spusti verziu appky z mena zálohy. Príkaz odloží databázu aj "
                "so súbormi %s do %s a zálohu skopíruje na jej miesto. Ručne: zmaž vedľa "
                "databázy súbory %s, ak tam sú, a skopíruj zálohu na miesto databázy %s.",
                exc,
                saved,
                restore,
                restore,
                leftovers,
                saved.parent,
                leftovers,
                db_path,
            )
        raise
    if db_path is None:
        return saved
    if db_path.is_file():
        record_version(db_path, version)
    # Aj po štarte bez zálohy (vrátená záloha a predchádzajúca verzia): značka
    # by inak ukazovala na zálohu, ktorá k databáze už nepatrí.
    _forget_failure(db_path)
    # Po každom úspešnom štarte, aj bez novej zálohy: inak by staré zálohy
    # ostali, kým nevyjde nová verzia. Záloha tohto štartu a záloha zo značky,
    # ktorá nešla zmazať, ostanú bez ohľadu na vek.
    protect = [p for p in (saved, _marked_backup(db_path)) if p is not None]
    prune(db_path.parent / FOLDER, db_path.stem, protect=protect)
    return saved


# --- návrat zálohy (python -m lego_api.cli restore-backup) -------------------------


class RestoreFailed(RuntimeError):
    """Zálohu sa nepodarilo vrátiť; databáza ostala, ako bola."""


@dataclass(frozen=True)
class Restored:
    """Čo ``restore_backup`` urobil."""

    source: Path
    database: Path
    #: Meno, pod ktoré sa odložila doterajšia databáza (v ``backups``).
    aside: Path
    #: Súbory, ktoré sa naozaj odložili (databáza a jej žurnál), a kam.
    moved: tuple[tuple[Path, Path], ...]
    #: Revízia a verzia appky v zálohe; verzia None = nezapísaná (spred 1.0.0).
    revision: str
    version: str | None


def find_backup(db_path: Path, name: str) -> Path:
    """Súbor zálohy z príkazového riadku; samotné meno sa hľadá aj v ``backups``."""
    path = Path(name)
    if not path.exists() and path.name == name:
        candidate = db_path.parent / FOLDER / name
        if candidate.exists():
            return candidate
    return path


def _open_readonly(path: Path) -> sqlite3.Connection:
    """Len na čítanie: chýbajúci súbor nezaloží a zálohu nezmení."""
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _check_backup(source: Path) -> tuple[str, str | None]:
    """Revízia a verzia zálohy; súbor, ktorý nie je celá databáza appky, odmietne."""
    try:
        with closing(_open_readonly(source)) as conn:
            problems = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
            if problems != ["ok"]:
                raise RestoreFailed(
                    f"Súbor {source} je poškodená databáza ({'; '.join(problems[:3])})."
                )
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
            ).fetchone()
            rows = []
            if table is not None:
                rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
            version = _version_of(conn)
    except sqlite3.Error as exc:
        raise RestoreFailed(f"Súbor {source} nie je čitateľná databáza SQLite ({exc}).") from exc
    revisions = sorted(row[0] for row in rows if row[0])
    if not revisions:
        raise RestoreFailed(
            f"Súbor {source} nie je databáza appky Moje kocky (chýba alembic_version)."
        )
    return "_".join(revisions), version


def _aside_path(db_path: Path, now: datetime) -> Path:
    """Voľné meno v ``backups`` pre doterajšiu databázu aj jej žurnál.

    Tvar mena je ako pri zálohe, takže ju rotácia a vek zmažú ako zálohu.
    """
    folder = db_path.parent / FOLDER
    base = f"{db_path.stem}-{now.strftime(_STAMP)}-{ASIDE_LABEL}"
    candidate, number = folder / f"{base}.db", 1
    while any(p.exists() for p in _with_sidecars(candidate)):
        number += 1
        candidate = folder / f"{base}-{number}.db"
    return candidate


def _copy_into_place(source: Path, db_path: Path) -> None:
    """Zálohu skopíruje zálohovacím API SQLite; na miesto ide až hotová kópia."""
    partial = db_path.with_name(db_path.name + ".part")
    try:
        with closing(_open_readonly(source)) as src, closing(sqlite3.connect(partial)) as dst:
            _copy(src, dst)
        os.replace(partial, db_path)
    except BaseException:
        with suppress(OSError):
            partial.unlink(missing_ok=True)
        raise


def restore_backup(db_path: Path, source: Path, *, now: datetime | None = None) -> Restored:
    """Vráti zálohu ``source`` na miesto databázy ``db_path``. Appka musí stáť.

    Doterajšia databáza sa nemaže: aj so zvyškami žurnálu ide do ``backups``
    pod meno ``lego-RRRRMMDD-HHMMSS-pred-obnovou.db`` (žurnál vedľa nej s tým
    istým menom, takže sa dá otvoriť, ako bola). Bez toho by SQLite žurnál
    pokazenej databázy vrátil do obnovenej. Súbor, ktorý nie je celá
    databáza appky, odmietne; keď niečo zlyhá, všetko vráti na miesto.
    """
    if not source.is_file():
        raise RestoreFailed(f"Záloha {source} neexistuje alebo nie je súbor.")
    if db_path.exists() and os.path.samefile(source, db_path):
        raise RestoreFailed(f"Súbor {source} je samotná databáza, nie jej záloha.")
    revision, version = _check_backup(source)
    aside = _aside_path(db_path, now or datetime.now())
    moved: list[tuple[Path, Path]] = []
    try:
        aside.parent.mkdir(parents=True, exist_ok=True)
        for original, target in zip(_with_sidecars(db_path), _with_sidecars(aside), strict=True):
            if original.exists():
                shutil.move(original, target)
                moved.append((original, target))
        _copy_into_place(source, db_path)
    except (OSError, sqlite3.Error) as exc:
        left: list[Path] = []
        for original, target in reversed(moved):
            try:
                shutil.move(target, original)
            except OSError:
                left.append(target)
        where = (
            f"Pôvodné súbory ostali v {', '.join(map(str, left))}."
            if left
            else "Databáza ostala, ako bola."
        )
        raise RestoreFailed(
            f"Zálohu {source} sa nepodarilo vrátiť ({exc}). {where} "
            "Beží ešte appka? Zastav ju a skús znova."
        ) from exc
    return Restored(source, db_path, aside, tuple(moved), revision, version)
