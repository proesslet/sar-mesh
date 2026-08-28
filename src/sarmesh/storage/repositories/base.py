import sqlite3
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sarmesh.storage.database import Database


class Repository:
    def __init__(self, database: "Database") -> None:
        self._database = database

    def _transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        return self._database.transaction()
