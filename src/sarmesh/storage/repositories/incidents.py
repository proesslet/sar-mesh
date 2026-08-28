from datetime import UTC, datetime
from uuid import uuid4

from sarmesh.core.models import Incident
from sarmesh.storage import mappers
from sarmesh.storage.repositories.base import Repository


class IncidentRepository(Repository):
    def create(self, name: str) -> Incident:
        incident = Incident(id=str(uuid4()), name=name, started_at=datetime.now(UTC))

        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO incidents (id, name, started_at, ended_at)
                VALUES (?, ?, ?, ?)
                """,
                (incident.id, incident.name, incident.started_at.isoformat(), None),
            )

        return incident

    def get(self, incident_id: str) -> Incident | None:
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT id, name, started_at, ended_at FROM incidents WHERE id = ?
                """,
                (incident_id,),
            ).fetchone()

        return mappers.incident(row) if row else None

    def list(self) -> list[Incident]:
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, name, started_at, ended_at FROM incidents
                ORDER BY started_at DESC
                """
            ).fetchall()

        return [mappers.incident(row) for row in rows]

    def active(self) -> Incident | None:
        """The incident positions are currently recorded against.

        The newest un-ended one wins. Only one can be active at a time.
        """
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT id, name, started_at, ended_at FROM incidents
                WHERE ended_at IS NULL
                ORDER BY started_at DESC LIMIT 1
                """
            ).fetchone()

        return mappers.incident(row) if row else None

    def update(self, incident_id: str, name: str) -> Incident | None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE incidents SET name = ? WHERE id = ?",
                (name, incident_id),
            )

        return self.get(incident_id)

    def end(self, incident_id: str, ended_at: datetime) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE incidents SET ended_at = ? WHERE id = ?",
                (ended_at.isoformat(), incident_id),
            )
