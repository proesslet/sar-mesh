"""Connection lifecycle and schema migration."""

import sqlite3
from pathlib import Path

import pytest

from sarmesh.storage.database import Database
from sarmesh.storage.schema import MIGRATIONS


def test_migrate_creates_every_table(database: Database) -> None:
    with database.transaction() as connection:
        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "positions",
        "incidents",
        "trackers",
        "teams",
        "tracker_assignments",
        "settings",
    } <= names


def test_migrate_stamps_the_current_version(database: Database) -> None:
    with database.transaction() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == len(MIGRATIONS)


def test_migrate_is_idempotent(database: Database) -> None:
    """Every start calls migrate(); the second one must be a no-op."""
    database.migrate()
    database.migrate()

    with database.transaction() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == len(MIGRATIONS)


def test_migrate_refuses_a_newer_schema(database_path: Path) -> None:
    """An older build must not operate on a database it does not understand."""
    connection = sqlite3.connect(database_path)
    connection.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    connection.commit()
    connection.close()

    database = Database(database_path)

    try:
        with pytest.raises(RuntimeError, match="Upgrade SARMesh"):
            database.migrate()
    finally:
        database.close()


def test_migrate_creates_a_missing_parent_directory(tmp_path: Path) -> None:
    """A packaged build's user data directory does not exist on first run."""
    database = Database(tmp_path / "nested" / "dir" / "sarmesh.db")

    try:
        database.migrate()
    finally:
        database.close()

    assert (tmp_path / "nested" / "dir" / "sarmesh.db").is_file()


def test_querying_a_closed_database_raises(database: Database) -> None:
    """Silently reconnecting on shutdown is what leaves WAL sidecars behind."""
    database.close()

    with pytest.raises(RuntimeError, match="closed"):
        database.incidents.list()


def test_close_is_safe_to_call_twice(database: Database) -> None:
    database.close()
    database.close()


def test_transaction_nests_without_deadlocking(database: Database) -> None:
    """Repositories call each other; an exclusive lock would hang here."""
    incident = database.incidents.create("Ridgeline")

    with database.transaction():
        assert database.incidents.get(incident.id) is not None
