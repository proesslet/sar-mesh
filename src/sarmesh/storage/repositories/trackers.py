from sarmesh.core.models import Tracker
from sarmesh.storage import mappers
from sarmesh.storage.repositories.base import Repository


class TrackerRepository(Repository):
    def create(self, node_id: str, label: str) -> Tracker:
        tracker = Tracker(node_id=node_id, label=label)

        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO trackers (node_id, label) VALUES (?, ?)",
                (tracker.node_id, tracker.label),
            )

        return tracker

    def get(self, node_id: str) -> Tracker | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT node_id, label FROM trackers WHERE node_id = ?",
                (node_id,),
            ).fetchone()

        return mappers.tracker(row) if row else None

    def list(self) -> list[Tracker]:
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT node_id, label FROM trackers ORDER BY label"
            ).fetchall()

        return [mappers.tracker(row) for row in rows]

    def update(self, node_id: str, label: str) -> Tracker | None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE trackers SET label = ? WHERE node_id = ?",
                (label, node_id),
            )

        return self.get(node_id)

    def delete(self, node_id: str) -> None:
        with self._transaction() as connection:
            connection.execute("DELETE FROM trackers WHERE node_id = ?", (node_id,))
