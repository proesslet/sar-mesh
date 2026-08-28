from datetime import UTC, datetime

from sarmesh.core.models import TrackerAssignment
from sarmesh.storage import mappers
from sarmesh.storage.repositories.base import Repository

SELECT_ASSIGNMENT = """
    SELECT incident_id, tracker_node_id, team_id, assigned_at, unassigned_at
    FROM tracker_assignments
"""


class AssignmentRepository(Repository):
    """Which team is carrying which tracker, and which team used to.

    Assignments are historical. Releasing a tracker stamps unassigned_at rather
    than deleting the row, so an incident's attribution can be reconstructed
    afterwards.
    """

    def create(
        self, incident_id: str, tracker_node_id: str, team_id: str
    ) -> TrackerAssignment:
        assignment = TrackerAssignment(
            incident_id=incident_id,
            tracker_node_id=tracker_node_id,
            team_id=team_id,
            assigned_at=datetime.now(UTC),
        )

        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO tracker_assignments (
                    incident_id, tracker_node_id, team_id, assigned_at, unassigned_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    assignment.incident_id,
                    assignment.tracker_node_id,
                    assignment.team_id,
                    assignment.assigned_at.isoformat(),
                    None,
                ),
            )

        return assignment

    def active_for(self, tracker_node_id: str) -> TrackerAssignment | None:
        """Whatever is currently holding this tracker, if anything."""
        with self._transaction() as connection:
            row = connection.execute(
                SELECT_ASSIGNMENT
                + """
                WHERE tracker_node_id = ? AND unassigned_at IS NULL
                ORDER BY assigned_at DESC LIMIT 1
                """,
                (tracker_node_id,),
            ).fetchone()

        return mappers.assignment(row) if row else None

    def active_for_incident(self, incident_id: str) -> list[TrackerAssignment]:
        with self._transaction() as connection:
            rows = connection.execute(
                SELECT_ASSIGNMENT
                + """
                WHERE incident_id = ? AND unassigned_at IS NULL
                ORDER BY assigned_at DESC
                """,
                (incident_id,),
            ).fetchall()

        return [mappers.assignment(row) for row in rows]

    def list_active(self) -> list[TrackerAssignment]:
        """Every assignment still in force, across all incidents."""
        with self._transaction() as connection:
            rows = connection.execute(
                SELECT_ASSIGNMENT
                + """
                WHERE unassigned_at IS NULL ORDER BY assigned_at DESC
                """
            ).fetchall()

        return [mappers.assignment(row) for row in rows]

    def release(self, tracker_node_id: str, unassigned_at: datetime) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE tracker_assignments
                SET unassigned_at = ?
                WHERE tracker_node_id = ? AND unassigned_at IS NULL
                """,
                (unassigned_at.isoformat(), tracker_node_id),
            )
