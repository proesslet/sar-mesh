from uuid import uuid4

from sarmesh.core.models import Team
from sarmesh.storage import mappers
from sarmesh.storage.repositories.base import Repository


class TeamRepository(Repository):
    def create(self, name: str, personnel_count: int) -> Team:
        team = Team(id=str(uuid4()), name=name, personnel_count=personnel_count)

        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO teams (id, name, personnel_count)
                VALUES (?, ?, ?)
                """,
                (team.id, team.name, team.personnel_count),
            )

        return team

    def get(self, team_id: str) -> Team | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT id, name, personnel_count FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()

        return mappers.team(row) if row else None

    def list(self) -> list[Team]:
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT id, name, personnel_count FROM teams ORDER BY name"
            ).fetchall()

        return [mappers.team(row) for row in rows]

    def update(
        self,
        team_id: str,
        name: str | None = None,
        personnel_count: int | None = None,
    ) -> Team | None:
        """Change whichever fields were supplied, leaving the rest alone."""
        with self._transaction() as connection:
            if name is not None:
                connection.execute(
                    "UPDATE teams SET name = ? WHERE id = ?", (name, team_id)
                )

            if personnel_count is not None:
                connection.execute(
                    "UPDATE teams SET personnel_count = ? WHERE id = ?",
                    (personnel_count, team_id),
                )

        return self.get(team_id)

    def delete(self, team_id: str) -> None:
        with self._transaction() as connection:
            connection.execute("DELETE FROM teams WHERE id = ?", (team_id,))
