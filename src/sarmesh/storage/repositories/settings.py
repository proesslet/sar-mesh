from sarmesh.storage.repositories.base import Repository


class SettingsRepository(Repository):
    """Operator preferences that outlive a run, as key/value text."""

    def get(self, key: str) -> str | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()

        return row["value"] if row is not None else None

    def set(self, key: str, value: str | None) -> None:
        """Store a preference, or clear it when value is None."""
        with self._transaction() as connection:
            if value is None:
                connection.execute("DELETE FROM settings WHERE key = ?", (key,))
                return

            connection.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
