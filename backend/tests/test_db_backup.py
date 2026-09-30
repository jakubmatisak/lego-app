"""Záloha databázy pri aktualizácii appky.

Pri prvom štarte novej verzie sa databáza sama zmigruje. Keď migrácia
niečo zmení, alebo nad databázou naposledy bežala iná verzia appky, najprv
vznikne kópia v ``backups`` vedľa databázy.
"""

import json
import logging
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from lego_api.services import db_backup

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"
#: Prvá migrácia, existuje vždy a nikdy nebude head.
OLD = "9a38f007d771"
NAME = re.compile(r"^lego-\d{8}-\d{6}-9a38f007d771\.db$")
#: Verzia appky, ktorá nad databázou bežala predtým, a tá, ktorá sa spúšťa.
PREV = "0.9.0"
NEW = "1.0.0"


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return config


def _head() -> str:
    (head,) = db_backup.head_revisions(_config())
    return head


def _url(path: Path | str) -> str:
    return f"sqlite+aiosqlite:///{path}"


def _make_db(path: Path, revision: str | None, rows=("10294-1", "71046-1")) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE sety (num TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO sety VALUES (?)", [(r,) for r in rows])
        if revision is not None:
            conn.execute(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
            conn.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        conn.commit()


_APP_SETTINGS = (
    "CREATE TABLE IF NOT EXISTS app_settings (key VARCHAR(64) NOT NULL PRIMARY KEY, "
    "value JSON NOT NULL, updated_at DATETIME NOT NULL)"
)


def _settings_table(path: Path, **rows: str) -> None:
    """Tabuľka ``app_settings`` ako v skutočnej databáze; hodnoty sú surový JSON."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(_APP_SETTINGS)
        conn.executemany(
            "INSERT OR REPLACE INTO app_settings VALUES (?, ?, '2026-09-01 10:00:00')",
            list(rows.items()),
        )
        conn.commit()


def _stamp_version(path: Path, version: str) -> None:
    """Verzia zapísaná tak, ako ju po štarte necháva appka."""
    _settings_table(path, app_version=json.dumps(version))


def _version_in(path: Path) -> str | None:
    rows = _read(path, "SELECT value FROM app_settings WHERE key = 'app_version'")
    return json.loads(rows[0][0]) if rows else None


def _read(path: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def _backups(db: Path) -> list[str]:
    """Súbory v priečinku záloh okrem značky o zlyhanej migrácii."""
    folder = db.parent / "backups"
    if not folder.is_dir():
        return []
    marker = db_backup.failure_marker(db)
    return sorted(p.name for p in folder.iterdir() if p != marker)


class _Clock:
    """Každé ``now()`` o sekundu neskôr, nech majú zálohy rôzne mená."""

    start = datetime(2026, 9, 30, 8, 0, 0)
    calls = 0

    @classmethod
    def now(cls) -> datetime:
        cls.calls += 1
        return cls.start + timedelta(seconds=cls.calls)


@pytest.fixture
def clock(monkeypatch):
    _Clock.calls = 0
    monkeypatch.setattr(db_backup, "datetime", _Clock)
    return _Clock


@pytest.fixture
def restore_logging():
    """Skutočný ``command.upgrade`` môže prekonfigurovať logovanie; test po sebe uprace."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    disabled = {
        name: logger.disabled
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    for name, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.disabled = disabled.get(name, False)


# --- cesta k databáze ------------------------------------------------------


def test_sqlite_path_from_url():
    assert db_backup.sqlite_path("sqlite+aiosqlite:///./data/lego.db") == Path("./data/lego.db")
    assert db_backup.sqlite_path("sqlite+aiosqlite:////app/data/lego.db") == Path(
        "/app/data/lego.db"
    )
    assert db_backup.sqlite_path(r"sqlite+aiosqlite:///C:\Data\Moje Kocky\lego.db") == Path(
        r"C:\Data\Moje Kocky\lego.db"
    )


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite:///:memory:",
        "sqlite+aiosqlite://",
        "sqlite+aiosqlite:///file:mem?mode=memory&cache=shared&uri=true",
        "postgresql://u:p@localhost/lego",
    ],
)
def test_no_file_for_memory_or_other_engine(url):
    assert db_backup.sqlite_path(url) is None


# --- kedy zálohovať ----------------------------------------------------------


def test_backup_created_at_old_revision(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    backup = db_backup.backup_before_upgrade(_url(db), _config())

    assert backup is not None
    assert backup.parent == tmp_path / "backups"
    assert NAME.match(backup.name), backup.name
    assert _backups(db) == [backup.name]


def test_backup_is_readable_copy_with_same_data(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, OLD, rows=("10294-1", "42233-3", "71046-1"))

    backup = db_backup.backup_before_upgrade(_url(db), _config())

    assert backup is not None
    assert _read(backup, "SELECT num FROM sety ORDER BY num") == _read(
        db, "SELECT num FROM sety ORDER BY num"
    )
    assert _read(backup, "SELECT version_num FROM alembic_version") == [(OLD,)]
    assert _read(backup, "PRAGMA integrity_check") == [("ok",)]


def test_backup_consistent_while_connection_is_open(tmp_path):
    """Appka môže mať spojenie otvorené; záloha vidí potvrdené údaje."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO sety VALUES ('75192-1')")
        conn.commit()

        backup = db_backup.backup_before_upgrade(_url(db), _config())

        assert backup is not None
        assert ("75192-1",) in _read(backup, "SELECT num FROM sety")


def test_no_backup_at_head_with_same_version(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, NEW)

    assert db_backup.backup_before_upgrade(_url(db), _config(), version=NEW) is None
    assert not (tmp_path / "backups").exists()


def test_no_backup_for_missing_database(tmp_path):
    db = tmp_path / "lego.db"

    assert db_backup.backup_before_upgrade(_url(db), _config()) is None
    assert not db.exists(), "kontrola nesmie založiť prázdny súbor"
    assert not (tmp_path / "backups").exists()


def test_no_backup_for_database_without_alembic_version(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, None)

    assert db_backup.backup_before_upgrade(_url(db), _config()) is None
    assert not (tmp_path / "backups").exists()


def test_no_backup_for_empty_alembic_version(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("DELETE FROM alembic_version")
        conn.commit()

    assert db_backup.backup_before_upgrade(_url(db), _config()) is None


def test_no_backup_for_empty_file(tmp_path):
    db = tmp_path / "lego.db"
    db.touch()

    assert db_backup.backup_before_upgrade(_url(db), _config()) is None


def test_no_backup_in_memory():
    assert db_backup.backup_before_upgrade("sqlite+aiosqlite:///:memory:", _config()) is None


# --- nová verzia appky bez zmeny schémy ------------------------------------------


def test_new_version_without_migration_backs_up(tmp_path, clock):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert saved is not None
    # V mene je verzia, ktorá databázu nechala, a revízia, na ktorej stojí.
    assert saved.name == f"lego-20260930-080001-v{PREV}-{_head()}.db"
    assert _read(saved, "SELECT num FROM sety ORDER BY num") == [("10294-1",), ("71046-1",)]
    assert _version_in(saved) == PREV, "záloha je stav spred aktualizácie"
    assert _version_in(db) == NEW


def test_older_version_backs_up_too(tmp_path, clock):
    """Návrat na staršiu verziu je tiež zmena, databázu nad ňou čaká iný kód."""
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, "1.1.0")

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert saved is not None
    assert saved.name == f"lego-20260930-080001-v1.1.0-{_head()}.db"
    assert _version_in(db) == NEW


def test_second_start_of_same_version_makes_no_backup(tmp_path, clock):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)

    first = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)
    second = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert first is not None
    assert second is None
    assert _backups(db) == [first.name]


def test_database_without_recorded_version_backs_up(tmp_path, clock):
    """Inštalácia spred zapisovania verzie: prvý štart novej verzie nad ňou."""
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _settings_table(db, allow_registration="true")

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert saved is not None
    assert saved.name == f"lego-20260930-080001-{_head()}.db"
    assert _version_in(db) == NEW
    assert _read(db, "SELECT value FROM app_settings WHERE key = 'allow_registration'") == [
        ("true",)
    ]


def test_old_revision_without_settings_table_backs_up(tmp_path, clock):
    """Revízia spred tabuľky ``app_settings``: verzia sa nedá zistiť, zálohuje sa."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    saved = db_backup.backup_before_upgrade(_url(db), _config(), version=NEW)

    assert saved is not None
    assert NAME.match(saved.name), saved.name


@pytest.mark.parametrize("raw", ["nie je json", "42", "null", '{"v": "1.0.0"}'])
def test_unreadable_recorded_version_counts_as_unknown(tmp_path, clock, raw):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _settings_table(db, app_version=raw)

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert saved is not None
    assert saved.name == f"lego-20260930-080001-{_head()}.db"
    assert _version_in(db) == NEW


def test_version_with_odd_characters_gives_safe_name(tmp_path, clock):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, "1.0.0+dev/../x")

    saved = db_backup.backup_before_upgrade(_url(db), _config(), version=NEW)

    assert saved is not None
    assert saved.parent == tmp_path / "backups"
    assert saved.name == f"lego-20260930-080001-v1.0.0_dev_.._x-{_head()}.db"


def test_version_is_recorded_only_after_successful_upgrade(tmp_path, clock):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)

    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken, version=NEW)

    assert _version_in(db) == PREV


def test_restart_loop_after_new_version_keeps_single_backup(tmp_path, clock):
    """Štart novej verzie padá dookola a zakaždým niečo zapíše (Docker ``restart``)."""
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)
    attempts = 0

    def broken() -> None:
        nonlocal attempts
        attempts += 1
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("INSERT INTO sety VALUES (?)", (f"POKAZENE-{attempts}",))
            conn.commit()
        raise RuntimeError("štart spadol")

    for _ in range(7):
        with pytest.raises(RuntimeError):
            db_backup.upgrade_with_backup(_url(db), _config(), broken, version=NEW)

    assert attempts == 7
    (name,) = _backups(db)
    assert name == f"lego-20260930-080001-v{PREV}-{_head()}.db"
    backup = tmp_path / "backups" / name
    assert _read(backup, "SELECT num FROM sety ORDER BY num") == [("10294-1",), ("71046-1",)]

    # Keď sa štart podarí, verzia sa zapíše a značka o zlyhaní zmizne.
    assert db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW) == backup
    assert _version_in(db) == NEW
    assert not db_backup.failure_marker(db).exists()
    assert _backups(db) == [name]


def test_new_version_backup_failure_prevents_upgrade(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)
    (tmp_path / "backups").write_text("nie som priečinok")
    calls: list[str] = []

    with pytest.raises(db_backup.BackupFailed):
        db_backup.upgrade_with_backup(
            _url(db), _config(), lambda: calls.append("upgrade"), version=NEW
        )

    assert calls == []
    assert _version_in(db) == PREV


def test_new_database_gets_no_backup_but_records_version(tmp_path):
    """Úplne nová inštalácia: nie je čo zálohovať, verzia sa zapíše pre ďalší štart."""
    db = tmp_path / "lego.db"

    def create() -> None:
        _make_db(db, _head(), rows=())
        _settings_table(db)

    assert db_backup.upgrade_with_backup(_url(db), _config(), create, version=NEW) is None
    assert not (tmp_path / "backups").exists()
    assert _version_in(db) == NEW


def test_missing_settings_table_after_upgrade_only_warns(tmp_path, clock, caplog):
    """Zápis verzie je evidencia; keď sa nepodarí, appka aj tak nabehne."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    with caplog.at_level(logging.WARNING, logger="lego_api.services.db_backup"):
        saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert saved is not None
    assert "Verziu appky" in caplog.text


# --- ponechanie posledných piatich -------------------------------------------


def _old_backups(tmp_path: Path) -> tuple[list[str], list[str]]:
    folder = tmp_path / "backups"
    folder.mkdir()
    old = [f"lego-2026010{d}-120000-{OLD}.db" for d in range(1, 7)]
    foreign = [
        "poznamka.txt",
        "lego-rucna-kopia.db",
        "ina-20260101-120000-9a38f007d771.db",
        "lego-20260101-120000-9a38f007d771.db.bak",
    ]
    for name in old + foreign:
        (folder / name).write_bytes(b"x")
    return old, foreign


def _broken() -> None:
    raise RuntimeError("migrácia spadla")


def test_keeps_five_newest_and_leaves_foreign_files(tmp_path, clock):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    old, foreign = _old_backups(tmp_path)

    backup = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None)

    assert backup is not None
    assert backup.name == f"lego-20260930-080001-{OLD}.db"
    assert _backups(db) == sorted([backup.name, *old[-4:], *foreign])


def test_rotation_counts_backups_with_and_without_version(tmp_path, clock):
    """Zálohy s verziou v mene aj staršie bez nej sú jeden rad, ostane päť najnovších."""
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)
    folder = tmp_path / "backups"
    folder.mkdir()
    without = [f"lego-2026010{d}-120000-{OLD}.db" for d in (1, 3, 5)]
    with_version = [f"lego-2026010{d}-120000-v0.{d}.0-{OLD}.db" for d in (2, 4, 6)]
    for name in without + with_version:
        (folder / name).write_bytes(b"x")
    (folder / "poznamka.txt").write_bytes(b"x")

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=NEW)

    assert saved is not None
    newest_old = sorted(without + with_version)[-4:]
    assert _backups(db) == sorted([saved.name, *newest_old, "poznamka.txt"])


def test_failed_upgrade_deletes_no_backup(tmp_path, clock):
    """Staré zálohy sa mažú až po úspešnej migrácii, nie pred ňou."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    old, foreign = _old_backups(tmp_path)

    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken)

    assert _backups(db) == sorted([f"lego-20260930-080001-{OLD}.db", *old, *foreign])


def test_repeated_failed_upgrade_keeps_backup_from_before_update(tmp_path, clock, caplog):
    """Slučka reštartov po zlyhanej migrácii (Docker, opakované spustenie desktopu).

    Migrácia pri každom pokuse niečo zapíše a spadne. Záloha spred aktualizácie
    musí ostať a kópie pokazeného stavu nemajú pribúdať.
    """
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    attempts = 0

    def broken() -> None:
        nonlocal attempts
        attempts += 1
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("INSERT INTO sety VALUES (?)", (f"POKAZENE-{attempts}",))
            conn.commit()
        raise RuntimeError("migrácia spadla")

    for _ in range(7):
        caplog.clear()
        with (
            caplog.at_level(logging.INFO, logger="lego_api.services.db_backup"),
            pytest.raises(RuntimeError),
        ):
            db_backup.upgrade_with_backup(_url(db), _config(), broken)

    assert attempts == 7
    (name,) = _backups(db)
    backup = tmp_path / "backups" / name
    assert _read(backup, "SELECT num FROM sety ORDER BY num") == [("10294-1",), ("71046-1",)]
    # Aj posledný pokus ukazuje na zálohu spred aktualizácie, nie na pokazenú kópiu.
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors and str(backup) in errors[-1]


def test_failure_after_first_committed_migration_keeps_backup(tmp_path, clock):
    """SQLite potvrdzuje každú migráciu zvlášť: prvá prejde, druhá spadne.

    Databáza potom stojí na medzirevízii. Ďalší štart ju nesmie zálohovať
    ako „stav pred aktualizáciou“; platí záloha zo starej revízie.
    """
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    def first_passes_second_fails() -> None:
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("UPDATE alembic_version SET version_num = 'c30e390ab49a'")
            conn.commit()
        raise RuntimeError("druhá migrácia spadla")

    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), first_passes_second_fails)
    for _ in range(6):
        with pytest.raises(RuntimeError):
            db_backup.upgrade_with_backup(_url(db), _config(), _broken)

    (name,) = _backups(db)
    assert NAME.match(name), name


def test_database_changed_after_failure_gets_new_backup(tmp_path, clock):
    """Po návrate zálohy a práci v starej verzii je databáza iná: zálohuje sa znova."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("INSERT INTO sety VALUES ('75192-1')")
        conn.commit()
    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken)

    first, second = _backups(db)
    assert ("75192-1",) not in _read(tmp_path / "backups" / first, "SELECT num FROM sety")
    assert ("75192-1",) in _read(tmp_path / "backups" / second, "SELECT num FROM sety")


def test_successful_upgrade_after_failure_forgets_it(tmp_path, clock):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken)
    assert db_backup.failure_marker(db).is_file()

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None)

    assert saved is not None
    assert not db_backup.failure_marker(db).exists()
    assert _backups(db) == [saved.name]


def test_start_without_backup_forgets_failure_too(tmp_path, clock):
    """Návrat zálohy a štart predchádzajúcej verzie: značka zmizne aj bez novej zálohy.

    Stará verzia nad vrátenou zálohou nemá čo zálohovať (head, jej verzia),
    no značka by inak ostala a ukazovala na zálohu, ktorá už k databáze
    nepatrí; po ďalšej práci v starej verzii by jej návrat zobral nové údaje.
    """
    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)
    with pytest.raises(RuntimeError):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken, version=NEW)
    (name,) = _backups(db)
    shutil.copy2(tmp_path / "backups" / name, db)

    saved = db_backup.upgrade_with_backup(_url(db), _config(), lambda: None, version=PREV)

    assert saved is None
    assert not db_backup.failure_marker(db).exists()
    assert _backups(db) == [name], "záloha ostáva, maže ju len rotácia"


# --- zlyhanie ------------------------------------------------------------------


def test_backup_failure_prevents_upgrade(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    # Priečinok zálohy sa nedá založiť: v ceste stojí súbor.
    (tmp_path / "backups").write_text("nie som priečinok")
    calls: list[str] = []

    with pytest.raises(db_backup.BackupFailed) as info:
        db_backup.upgrade_with_backup(_url(db), _config(), lambda: calls.append("upgrade"))

    assert calls == []
    assert "Migrácia sa nespustila" in str(info.value)
    assert _read(db, "SELECT version_num FROM alembic_version") == [(OLD,)]


def test_partial_backup_is_not_left_behind(tmp_path, monkeypatch):
    """Rozpísaná kópia (plný disk) nesmie vyzerať ako platná záloha."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    def full_disk(source, target):
        target.execute("CREATE TABLE polovica (x)")
        target.commit()
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(db_backup, "_copy", full_disk)

    with pytest.raises(db_backup.BackupFailed):
        db_backup.backup_before_upgrade(_url(db), _config())

    assert _backups(db) == []


def test_failed_upgrade_logs_backup_path_and_reraises(tmp_path, caplog):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    def broken() -> None:
        raise RuntimeError("migrácia spadla")

    with (
        caplog.at_level(logging.ERROR, logger="lego_api.services.db_backup"),
        pytest.raises(RuntimeError, match="migrácia spadla"),
    ):
        db_backup.upgrade_with_backup(_url(db), _config(), broken)

    (name,) = _backups(db)
    assert str(tmp_path / "backups" / name) in caplog.text


def test_failure_message_explains_restore_with_journal(tmp_path, caplog):
    """Po tvrdom páde ostane vedľa databázy žurnál; pred návratom zálohy musí preč."""
    db = tmp_path / "lego.db"
    _make_db(db, OLD)

    with (
        caplog.at_level(logging.ERROR, logger="lego_api.services.db_backup"),
        pytest.raises(RuntimeError),
    ):
        db_backup.upgrade_with_backup(_url(db), _config(), _broken)

    for leftover in ("lego.db-journal", "lego.db-wal", "lego.db-shm"):
        assert leftover in caplog.text


def test_upgrade_runs_after_backup(tmp_path):
    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    seen: list[list[str]] = []

    result = db_backup.upgrade_with_backup(_url(db), _config(), lambda: seen.append(_backups(db)))

    assert result is not None
    assert seen == [[result.name]], "záloha musí existovať skôr, než sa migrácia spustí"


# --- skutočné migrácie -----------------------------------------------------------


def test_real_migration_from_older_revision(tmp_path, settings, monkeypatch):
    """Databáza zmigrovaná Alembicom po staršiu revíziu, potom upgrade na head."""
    db = tmp_path / "lego.db"
    url = _url(db.as_posix())
    # env.py si URL berie z nastavení appky.
    monkeypatch.setattr(settings, "database_url", url)
    config = _config()
    older = "c30e390ab49a"
    command.upgrade(config, older)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, display_name, role, is_active, locale, "
            "created_at) VALUES ('otec@example.com', 'x', 'Jozef', 'admin', 1, 'sk', "
            "'2026-01-01 00:00:00')"
        )
        conn.commit()

    backup = db_backup.upgrade_with_backup(url, config, lambda: command.upgrade(config, "head"))

    assert backup is not None
    assert backup.name.endswith(f"-{older}.db")
    assert _read(backup, "SELECT version_num FROM alembic_version") == [(older,)]
    assert _read(backup, "SELECT email FROM users") == [("otec@example.com",)]
    assert _read(db, "SELECT version_num FROM alembic_version") == [(_head(),)]
    # Druhý štart už nič nemení, ďalšia záloha nevznikne.
    assert db_backup.upgrade_with_backup(url, config, lambda: None) is None
    assert _backups(db) == [backup.name]


def test_real_new_database_records_version_readable_by_app(tmp_path, settings, monkeypatch):
    """Nová databáza cez skutočné migrácie: bez zálohy, verzia v ``app_settings``.

    Zápis ide surovým SQL, preto test overí, že ho appka prečíta cez ORM
    ako každé iné nastavenie (JSON aj čas zmeny).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from lego_api.models import AppSetting

    db = tmp_path / "lego.db"
    url = _url(db.as_posix())
    monkeypatch.setattr(settings, "database_url", url)
    config = _config()

    def upgrade() -> None:
        command.upgrade(config, "head")

    assert db_backup.upgrade_with_backup(url, config, upgrade, version=NEW) is None
    assert not (tmp_path / "backups").exists()

    engine = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        with Session(engine) as session:
            row = session.get(AppSetting, db_backup.VERSION_KEY)
            assert row is not None
            assert row.value == NEW
            assert row.updated_at is not None
    finally:
        engine.dispose()

    # Tá istá verzia znova nič, ďalšia verzia zálohuje stav po tejto.
    assert db_backup.upgrade_with_backup(url, config, upgrade, version=NEW) is None
    saved = db_backup.upgrade_with_backup(url, config, upgrade, version="1.0.1")
    assert saved is not None
    assert saved.name.endswith(f"-v{NEW}-{_head()}.db")
    assert _version_in(db) == "1.0.1"


# --- zapojenie v main.py ----------------------------------------------------------


async def test_startup_does_not_migrate_when_backup_fails(tmp_path, settings, monkeypatch):
    from lego_api import main

    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    (tmp_path / "backups").write_text("nie som priečinok")
    monkeypatch.setattr(settings, "database_url", _url(db))
    calls: list[str] = []
    monkeypatch.setattr(command, "upgrade", lambda config, rev: calls.append(rev))

    with pytest.raises(db_backup.BackupFailed):
        await main._migrate()

    assert calls == []


async def test_failed_real_migration_at_startup_logs_backup(
    tmp_path, settings, monkeypatch, caplog, restore_logging
):
    """Skutočná migrácia cez alembic.ini: env.py nesmie vypnúť logger zálohy ani appky."""
    from lego_api import main

    db = tmp_path / "lego.db"
    # Revízia bez jej tabuliek: ďalšia migrácia spadne.
    _make_db(db, OLD)
    monkeypatch.setattr(settings, "database_url", _url(db.as_posix()))

    with caplog.at_level(logging.INFO), pytest.raises(Exception):  # noqa: B017, PT011
        await main._migrate()

    (name,) = _backups(db)
    backup = tmp_path / "backups" / name
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(str(backup) in e for e in errors), caplog.text
    for logger in ("lego_api.services.db_backup", "lego_api.main", "uvicorn.error"):
        assert not logging.getLogger(logger).disabled, logger


async def test_startup_backs_up_before_upgrade(tmp_path, settings, monkeypatch):
    from lego_api import main

    db = tmp_path / "lego.db"
    _make_db(db, OLD)
    monkeypatch.setattr(settings, "database_url", _url(db))
    seen: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(command, "upgrade", lambda config, rev: seen.append((rev, _backups(db))))

    await main._migrate()

    ((rev, names),) = seen
    assert rev == "head"
    assert len(names) == 1 and NAME.match(names[0])


async def test_startup_backs_up_when_app_version_changes(tmp_path, settings, monkeypatch):
    """Štart appky s inou verziou, než nad databázou bežala, zálohuje aj bez migrácie."""
    import lego_api
    from lego_api import main

    db = tmp_path / "lego.db"
    _make_db(db, _head())
    _stamp_version(db, PREV)
    monkeypatch.setattr(settings, "database_url", _url(db))
    monkeypatch.setattr(lego_api, "__version__", NEW)
    seen: list[list[str]] = []
    monkeypatch.setattr(command, "upgrade", lambda config, rev: seen.append(_backups(db)))

    await main._migrate()

    ((name,),) = seen
    assert re.fullmatch(rf"lego-\d{{8}}-\d{{6}}-v{re.escape(PREV)}-{_head()}\.db", name), name
    assert _version_in(db) == NEW
