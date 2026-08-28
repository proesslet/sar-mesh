"""The SQLite connection, and the repositories that query through it.

Database itself owns only the connection, its lock and the schema version. Every
query lives on one of the repositories hanging off it, reached as
`database.incidents.get(...)`, `database.teams.list()` and so on.
"""

import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sarmesh.storage.repositories.assignments import AssignmentRepository
from sarmesh.storage.repositories.incidents import IncidentRepository
from sarmesh.storage.repositories.positions import PositionRepository
from sarmesh.storage.repositories.settings import SettingsRepository
from sarmesh.storage.repositories.teams import TeamRepository
from sarmesh.storage.repositories.trackers import TrackerRepository
from sarmesh.storage.schema import MIGRATIONS


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._closed = False

        self.incidents = IncidentRepository(self)
        self.teams = TeamRepository(self)
        self.trackers = TrackerRepository(self)
        self.assignments = AssignmentRepository(self)
        self.positions = PositionRepository(self)
        self.settings = SettingsRepository(self)

    def connect(self) -> sqlite3.Connection:
        # A query after close is a bug, not a race worth tolerating. Without
        # this the None connection reads as "not opened yet" and silently
        # reconnects, which on shutdown leaves the WAL sidecars behind.
        if self._closed:
            raise RuntimeError(f"The database at {self.path} is closed")

        if self._connection is None:
            # sqlite3 creates the file but not a missing parent, and a packaged
            # app's user data directory does not exist on first run.
            self.path.parent.mkdir(parents=True, exist_ok=True)

            # Positions arrive on the Meshtastic publishing thread while the
            # main thread owns the CLI, so one connection is shared across
            # threads and serialised by self._lock instead.
            connection = sqlite3.connect(self.path, check_same_thread=False)

            # So the mappers survive a column being inserted mid-table.
            connection.row_factory = sqlite3.Row

            # The radio thread writes while the HTTP thread reads, and a
            # rollback journal would block every reader for the duration.
            connection.execute("PRAGMA journal_mode=WAL")

            # Durable across a process crash; only a power cut loses the last
            # commits. Worth it on an SD card, and the next beacon is seconds
            # away anyway.
            connection.execute("PRAGMA synchronous=NORMAL")

            # No table declares REFERENCES yet, so this enforces nothing
            # today. It is on so that adding constraints is a migration only.
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")

            self._connection = connection

        return self._connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        # An RLock, not a Lock: a repository method that calls another one
        # would otherwise deadlock on itself.
        with self._lock:
            connection = self.connect()
            with connection:
                yield connection

    def close(self) -> None:
        with self._lock:
            self._closed = True

            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def migrate(self) -> None:
        """Bring the database up to the current schema version.

        Safe on a fresh file and on one written by an older build alike: a new
        database reports user_version 0, so it simply runs every migration.
        """
        with self.transaction() as connection:
            current: int = connection.execute("PRAGMA user_version").fetchone()[0]

            if current > len(MIGRATIONS):
                # Written by a newer SARMesh. Refusing beats operating on a
                # schema this build does not understand, since silently
                # ignoring unknown columns is how incident data gets corrupted.
                raise RuntimeError(
                    f"{self.path} is at schema version {current}, but this "
                    f"build only knows version {len(MIGRATIONS)}. "
                    "Upgrade SARMesh."
                )

            for version, statements in enumerate(MIGRATIONS, start=1):
                if version <= current:
                    continue

                for statement in statements:
                    connection.execute(statement)

                # PRAGMA does not accept bound parameters. `version` is a loop
                # index over a module constant, never user input.
                connection.execute(f"PRAGMA user_version = {version}")
