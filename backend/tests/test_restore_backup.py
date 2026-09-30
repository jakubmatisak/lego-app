"""Návrat zálohy príkazom ``python -m lego_api.cli restore-backup <súbor>``.

Doterajšia databáza sa nemaže: aj so zvyškami žurnálu (``-journal``,
``-wal``, ``-shm``) ide do ``backups`` pod meno s časom, takže ju SQLite
nevráti do obnoveného súboru. Zálohu na jej miesto skopíruje zálohovacie
API SQLite. Súbor, ktorý nie je čitateľná databáza appky, príkaz odmietne
a nič nezmení.
"""

import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

from lego_api import cli
from lego_api.services import db_backup

OLD = "9a38f007d771"
SIDECARS = ("journal", "wal", "shm")
ASIDE = re.compile(r"^lego-\d{8}-\d{6}-pred-obnovou\.db$")


def _make_db(path: Path, rows, *, revision: str | None = OLD, version: str | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE sety (num TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO sety VALUES (?)", [(r,) for r in rows])
        if revision is not None:
            conn.execute(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
            conn.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        if version is not None:
            conn.execute(
                "CREATE TABLE app_settings (key VARCHAR(64) NOT NULL PRIMARY KEY, "
                "value JSON NOT NULL, updated_at DATETIME NOT NULL)"
            )
            conn.execute(
                "INSERT INTO app_settings VALUES ('app_version', ?, '2026-09-01 10:00:00')",
                (json.dumps(version),),
            )
        conn.commit()


def _rows(path: Path) -> list[tuple]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT num FROM sety ORDER BY num").fetchall()


def _run(capsys, *args: str) -> tuple[int, str, str]:
    try:
        cli.main(["restore-backup", *args])
        code = 0
    except SystemExit as exc:
        code = int(exc.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture
def setup(tmp_path):
    """Pokazená databáza so zvyškami žurnálu a záloha spred aktualizácie."""
    data = tmp_path / "data dáta"
    db = data / "lego.db"
    _make_db(db, ["POKAZENE"], revision="c30e390ab49a", version="1.0.0")
    for suffix in SIDECARS:
        (data / f"lego.db-{suffix}").write_bytes(suffix.encode())
    backup = data / "backups" / f"lego-20260915-083000-v1.0.0-{OLD}.db"
    _make_db(backup, ["10294-1", "71046-1"], version="1.0.0")
    return db, backup


def _asides(db: Path) -> list[Path]:
    folder = db.parent / "backups"
    return sorted(p for p in folder.iterdir() if ASIDE.match(p.name))


def _untouched(db: Path, before: bytes, backup: Path, backup_before: bytes) -> None:
    assert db.read_bytes() == before
    for suffix in SIDECARS:
        assert (db.parent / f"lego.db-{suffix}").read_bytes() == suffix.encode()
    assert backup.read_bytes() == backup_before
    assert _asides(db) == []


def test_restore_puts_backup_in_place_and_moves_current_aside(setup, capsys):
    db, backup = setup
    current = db.read_bytes()
    backup_bytes = backup.read_bytes()

    code, out, _err = _run(capsys, str(backup), "--database", str(db))

    assert code == 0
    # Žurnál pokazenej databázy pri obnovenej nesmie ostať, SQLite by ho do nej vrátil.
    for suffix in SIDECARS:
        assert not (db.parent / f"lego.db-{suffix}").exists(), suffix
    (aside,) = _asides(db)
    assert aside.read_bytes() == current, "doterajšia databáza sa nemaže, len odloží"
    for suffix in SIDECARS:
        assert (aside.parent / f"{aside.name}-{suffix}").read_bytes() == suffix.encode()
    assert backup.read_bytes() == backup_bytes, "záloha ostáva, kopíruje sa"
    assert _rows(db) == [("10294-1",), ("71046-1",)]
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    # Povie, čo urobil a čo ďalej: verzia zo zálohy a kam sa odložila databáza.
    assert str(aside) in out
    assert str(db) in out
    assert "1.0.0" in out
    assert "git checkout v1.0.0" in out


def test_restore_finds_backup_by_name_in_backups_folder(setup, capsys):
    db, backup = setup

    code, _out, _err = _run(capsys, backup.name, "--database", str(db))

    assert code == 0
    assert _rows(db) == [("10294-1",), ("71046-1",)]


def test_restore_takes_database_from_settings(setup, capsys, settings, monkeypatch):
    db, backup = setup
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db.as_posix()}")

    code, _out, _err = _run(capsys, str(backup))

    assert code == 0
    assert _rows(db) == [("10294-1",), ("71046-1",)]


def test_restore_refuses_file_that_is_not_a_database(setup, capsys):
    db, backup = setup
    backup.write_text("toto nie je databáza, ale poznámka", encoding="utf-8")
    before, backup_before = db.read_bytes(), backup.read_bytes()

    code, _out, err = _run(capsys, str(backup), "--database", str(db))

    assert code == 1
    assert "nie je" in err
    _untouched(db, before, backup, backup_before)


def test_restore_refuses_damaged_database(setup, capsys):
    db, backup = setup
    with closing(sqlite3.connect(backup)) as conn:
        conn.executemany("INSERT INTO sety VALUES (?)", [(f"{n:05d}-1" * 20,) for n in range(2000)])
        conn.commit()
    raw = bytearray(backup.read_bytes())
    raw[4096 * 2 : 4096 * 4] = b"\xa5" * (4096 * 2)
    backup.write_bytes(bytes(raw))
    before, backup_before = db.read_bytes(), backup.read_bytes()

    code, _out, err = _run(capsys, str(backup), "--database", str(db))

    assert code == 1
    assert err
    _untouched(db, before, backup, backup_before)


def test_restore_refuses_database_of_another_app(setup, capsys):
    db, backup = setup
    backup.unlink()
    _make_db(backup, ["10294-1"], revision=None)
    before, backup_before = db.read_bytes(), backup.read_bytes()

    code, _out, err = _run(capsys, str(backup), "--database", str(db))

    assert code == 1
    assert "alembic_version" in err
    _untouched(db, before, backup, backup_before)


def test_restore_refuses_empty_file(setup, capsys):
    """Prázdny súbor SQLite otvorí ako prázdnu databázu; zbierka by zmizla."""
    db, backup = setup
    backup.write_bytes(b"")
    before = db.read_bytes()

    code, _out, _err = _run(capsys, str(backup), "--database", str(db))

    assert code == 1
    _untouched(db, before, backup, b"")


def test_restore_refuses_missing_file_and_does_not_create_it(setup, capsys):
    db, backup = setup
    missing = backup.with_name("lego-20260101-000000-neexistuje.db")
    before, backup_before = db.read_bytes(), backup.read_bytes()

    code, _out, err = _run(capsys, str(missing), "--database", str(db))

    assert code == 1
    assert str(missing) in err
    assert not missing.exists()
    _untouched(db, before, backup, backup_before)


def test_restore_refuses_the_database_itself(setup, capsys):
    db, backup = setup
    before, backup_before = db.read_bytes(), backup.read_bytes()

    code, _out, _err = _run(capsys, str(db), "--database", str(db))

    assert code == 1
    _untouched(db, before, backup, backup_before)


def test_restore_without_current_database_moves_stray_journal_aside(setup, capsys):
    """Databáza chýba, žurnál po nej ostal: aj ten ide preč, inak by poškodil obnovenú."""
    db, backup = setup
    db.unlink()

    code, _out, _err = _run(capsys, str(backup), "--database", str(db))

    assert code == 0
    for suffix in SIDECARS:
        assert not (db.parent / f"lego.db-{suffix}").exists(), suffix
    assert _rows(db) == [("10294-1",), ("71046-1",)]
    moved = [p.name for p in (db.parent / "backups").iterdir() if "pred-obnovou" in p.name]
    assert len(moved) == len(SIDECARS)


def test_failed_copy_puts_everything_back(setup, capsys, monkeypatch):
    """Keď kopírovanie spadne (plný disk), doterajšia databáza sa vráti na miesto."""
    db, backup = setup
    before, backup_before = db.read_bytes(), backup.read_bytes()

    def full_disk(source, target):
        target.execute("CREATE TABLE polovica (x)")
        target.commit()
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(db_backup, "_copy", full_disk)

    code, _out, err = _run(capsys, str(backup), "--database", str(db))

    assert code == 1
    assert "disk is full" in err
    _untouched(db, before, backup, backup_before)
    assert sorted(p.name for p in db.parent.iterdir()) == sorted(
        ["backups", "lego.db", *(f"lego.db-{s}" for s in SIDECARS)]
    )


def test_backup_without_recorded_version_says_so(tmp_path, capsys):
    db = tmp_path / "lego.db"
    _make_db(db, ["POKAZENE"])
    backup = tmp_path / "backups" / f"lego-20260915-083000-{OLD}.db"
    _make_db(backup, ["10294-1"])

    code, out, _err = _run(capsys, str(backup), "--database", str(db))

    assert code == 0
    assert OLD in out
    assert "1.0.0" in out, "záloha bez verzie je z inštalácie spred 1.0.0"


def test_moved_aside_database_ages_out_like_backups(setup):
    """Odložená databáza je v ``backups`` ako záloha: po 90 dňoch ju štart zmaže aj so žurnálom."""
    db, backup = setup

    restored = db_backup.restore_backup(db, backup, now=datetime(2025, 1, 1, 12, 0, 0))

    assert restored.aside.name == "lego-20250101-120000-pred-obnovou.db"
    db_backup.prune(db.parent / "backups", db.stem)
    assert sorted(p.name for p in (db.parent / "backups").iterdir()) == [backup.name]


def test_second_restore_in_same_second_does_not_overwrite_first_aside(setup):
    db, backup = setup
    now = datetime(2026, 9, 30, 9, 0, 0)

    first = db_backup.restore_backup(db, backup, now=now)
    second = db_backup.restore_backup(db, backup, now=now)

    assert first.aside != second.aside
    assert first.aside.is_file() and second.aside.is_file()
