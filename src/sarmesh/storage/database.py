import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sarmesh.core.models import (
    Incident,
    Team,
    Tracker,
    TrackerAssignment,
    TrackerPosition,
    TrackerStatus,
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    ########################## Database Initialization ##########################

    def initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT,
                    node_id TEXT NOT NULL,
                    node_num INTEGER NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    received_at TEXT NOT NULL,
                    satellites INTEGER,
                    precision_bits INTEGER,
                    rssi INTEGER,
                    snr REAL
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS trackers (
                    node_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS teams (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    personnel_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tracker_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    tracker_node_id TEXT NOT NULL,
                    team_id TEXT NOT NULL,
                    assigned_at TEXT NOT NULL,
                    unassigned_at TEXT
                );
                """
            )

    ########################## Incident Management ##########################

    def create_incident(self, name: str) -> Incident:
        incident = Incident(
            id=str(uuid4()),
            name=name,
            started_at=datetime.now(UTC),
        )

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO incidents (id, name, started_at, ended_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    incident.id,
                    incident.name,
                    incident.started_at.isoformat(),
                    None,
                ),
            )
        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM incidents WHERE id = ?
                """,
                (incident_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                return Incident(
                    id=row[0],
                    name=row[1],
                    started_at=datetime.fromisoformat(row[2]),
                    ended_at=datetime.fromisoformat(row[3]) if row[3] else None,
                )
            return None

    def get_all_incidents(self) -> list[Incident]:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM incidents
                """
            )
            incidents = []
            for row in cursor.fetchall():
                incidents.append(
                    Incident(
                        id=row[0],
                        name=row[1],
                        started_at=datetime.fromisoformat(row[2]),
                        ended_at=datetime.fromisoformat(row[3]) if row[3] else None,
                    )
                )
            return incidents

    def get_active_incident(self) -> Incident | None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM incidents WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row is not None:
                return Incident(
                    id=row[0],
                    name=row[1],
                    started_at=datetime.fromisoformat(row[2]),
                    ended_at=None,
                )
            return None

    def end_incident(self, incident_id: str, ended_at: datetime) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE incidents
                SET ended_at = ?
                WHERE id = ?
                """,
                (ended_at.isoformat(), incident_id),
            )

    ########################### Team Management ##########################

    def create_team(self, name: str, personnel_count: int) -> Team:
        team = Team(
            id=str(uuid4()),
            name=name,
            personnel_count=personnel_count,
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO teams (id, name, personnel_count)
                VALUES (?, ?, ?)
                """,
                (team.id, team.name, team.personnel_count),
            )
        return team

    def get_team(self, team_id: str) -> Team | None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM teams WHERE id = ?
                """,
                (team_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                return Team(
                    id=row[0],
                    name=row[1],
                    personnel_count=row[2],
                )
            return None

    def get_all_teams(self) -> list[Team]:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM teams
                """
            )
            teams = []
            for row in cursor.fetchall():
                teams.append(
                    Team(
                        id=row[0],
                        name=row[1],
                        personnel_count=row[2],
                    )
                )
            return teams

    def update_team(
        self, team_id: str, name: str | None = None, personnel_count: int | None = None
    ) -> Team | None:
        with sqlite3.connect(self.path) as connection:
            if name is not None:
                connection.execute(
                    """
                    UPDATE teams
                    SET name = ?
                    WHERE id = ?
                    """,
                    (name, team_id),
                )
            if personnel_count is not None:
                connection.execute(
                    """
                    UPDATE teams
                    SET personnel_count = ?
                    WHERE id = ?
                    """,
                    (personnel_count, team_id),
                )
        return self.get_team(team_id)

    def delete_team(self, team_id: str) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                DELETE FROM teams WHERE id = ?
                """,
                (team_id,),
            )

    ############################ Tracker Management ##########################

    def create_tracker(self, node_id: str, label: str) -> Tracker:
        tracker = Tracker(
            node_id=node_id,
            label=label,
        )

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO trackers (node_id, label)
                VALUES (?, ?)
                """,
                (tracker.node_id, tracker.label),
            )

        return tracker

    def get_tracker(self, node_id: str) -> Tracker | None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM trackers WHERE node_id = ?
                """,
                (node_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                return Tracker(
                    node_id=row[0],
                    label=row[1],
                )
            return None

    def get_all_trackers(self) -> list[Tracker]:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM trackers
                """
            )
            trackers = []
            for row in cursor.fetchall():
                trackers.append(
                    Tracker(
                        node_id=row[0],
                        label=row[1],
                    )
                )
            return trackers

    def update_tracker(self, node_id: str, label: str) -> Tracker | None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE trackers
                SET label = ?
                WHERE node_id = ?
                """,
                (label, node_id),
            )
        return self.get_tracker(node_id)

    def delete_tracker(self, node_id: str) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                DELETE FROM trackers WHERE node_id = ?
                """,
                (node_id,),
            )

    ########################## Tracker Assignments ##########################

    def assign_tracker(
        self, incident_id: str, tracker_node_id: str, team_id: str
    ) -> TrackerAssignment:
        assignment = TrackerAssignment(
            incident_id=incident_id,
            tracker_node_id=tracker_node_id,
            team_id=team_id,
            assigned_at=datetime.now(UTC),
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO tracker_assignments (incident_id, tracker_node_id, team_id, assigned_at, unassigned_at)
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

    def get_active_assignment(self, tracker_node_id: str) -> TrackerAssignment | None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM tracker_assignments
                WHERE tracker_node_id = ? AND unassigned_at IS NULL ORDER BY assigned_at DESC LIMIT 1
                """,
                (tracker_node_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                return TrackerAssignment(
                    incident_id=row[1],
                    tracker_node_id=row[2],
                    team_id=row[3],
                    assigned_at=datetime.fromisoformat(row[4]),
                    unassigned_at=datetime.fromisoformat(row[5]) if row[5] else None,
                )
            return None

    def get_assignments_for_incident(self, incident_id: str) -> list[TrackerAssignment]:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM tracker_assignments
                WHERE incident_id = ? AND unassigned_at IS NULL ORDER BY assigned_at DESC
                """,
                (incident_id,),
            )
            rows = cursor.fetchall()
            return [
                TrackerAssignment(
                    incident_id=row[1],
                    tracker_node_id=row[2],
                    team_id=row[3],
                    assigned_at=datetime.fromisoformat(row[4]),
                    unassigned_at=datetime.fromisoformat(row[5]) if row[5] else None,
                )
                for row in rows
            ]

    def unassign_tracker(self, tracker_node_id: str, unassigned_at: datetime) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE tracker_assignments
                SET unassigned_at = ?
                WHERE tracker_node_id = ? AND unassigned_at IS NULL
                """,
                (unassigned_at.isoformat(), tracker_node_id),
            )

    ########################### Tracker Position Management ##########################

    def save_position(
        self, position: TrackerPosition, incident_id: str | None = None
    ) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO positions (
                    incident_id, 
                    node_id,
                    node_num,
                    latitude,
                    longitude,
                    received_at,
                    satellites,
                    precision_bits,
                    rssi,
                    snr
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    position.node_id,
                    position.node_num,
                    position.latitude,
                    position.longitude,
                    position.received_at.isoformat(),
                    position.satellites,
                    position.precision_bits,
                    position.rssi,
                    position.snr,
                ),
            )

    def get_latest_position(
        self, tracker_node_id: str, incident_id: str | None = None
    ) -> TrackerPosition | None:
        with sqlite3.connect(self.path) as connection:
            if incident_id is None:
                cursor = connection.execute(
                    """
                    SELECT * FROM positions
                    WHERE node_id = ?
                    ORDER BY received_at DESC
                    LIMIT 1
                    """,
                    (tracker_node_id,),
                )
            else:
                cursor = connection.execute(
                    """
                    SELECT * FROM positions
                    WHERE node_id = ? AND incident_id = ?
                    ORDER BY received_at DESC
                    LIMIT 1
                    """,
                    (tracker_node_id, incident_id),
                )
            row = cursor.fetchone()
            if row is not None:
                return TrackerPosition(
                    node_id=row[2],
                    node_num=row[3],
                    latitude=row[4],
                    longitude=row[5],
                    received_at=datetime.fromisoformat(row[6]),
                    satellites=row[7],
                    precision_bits=row[8],
                    rssi=row[9],
                    snr=row[10],
                )
            return None

    def list_latest_positions(self) -> list[TrackerPosition]:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                SELECT * FROM positions p1
                WHERE received_at = (
                    SELECT MAX(received_at) FROM positions p2
                    WHERE p1.node_id = p2.node_id
                )
                """
            )
            rows = cursor.fetchall()
            return [
                TrackerPosition(
                    node_id=row[2],
                    node_num=row[3],
                    latitude=row[4],
                    longitude=row[5],
                    received_at=datetime.fromisoformat(row[6]),
                    satellites=row[7],
                    precision_bits=row[8],
                    rssi=row[9],
                    snr=row[10],
                )
                for row in rows
            ]

    ############################ Tracker Status ##########################

    def get_tracker_status(
        self,
        tracker_node_id: str,
        incident_id: str | None = None,
    ) -> TrackerStatus | None:
        tracker = self.get_tracker(tracker_node_id)
        if tracker is None:
            return None

        assignment = self.get_active_assignment(tracker_node_id)

        if incident_id is not None and (
            assignment is None or assignment.incident_id != incident_id
        ):
            return None

        team = self.get_team(assignment.team_id) if assignment else None
        position = self.get_latest_position(tracker_node_id, incident_id=incident_id)

        return TrackerStatus(
            tracker=tracker,
            team=team,
            position=position,
            last_seen_at=position.received_at if position else None,
        )

    def list_incident_tracker_statuses(self, incident_id: str) -> list[TrackerStatus]:
        assignments = self.get_assignments_for_incident(incident_id)
        statuses = []
        for assignment in assignments:
            tracker_status = self.get_tracker_status(
                assignment.tracker_node_id, incident_id=incident_id
            )
            if tracker_status:
                statuses.append(tracker_status)
        return statuses
