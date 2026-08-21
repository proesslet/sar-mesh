import sqlite3
from pathlib import Path
from datetime import datetime

from sarmesh.core.models import TrackerPosition, TrackerAssignment, Incident, Tracker, Team


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

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

    def save_position(self, position: TrackerPosition) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO positions (
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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

    def get_active_assignment(self, tracker_node_id: str):
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

    def create_incident(self, incident: Incident) -> None:
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
                    incident.ended_at.isoformat() if incident.ended_at else None,
                ),
            )

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

    def create_tracker(self, tracker: Tracker) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO trackers (node_id, label)
                VALUES (?, ?)
                """,
                (tracker.node_id, tracker.label),
            )

    def create_team(self, team: Team) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO teams (id, name, personnel_count)
                VALUES (?, ?, ?)
                """,
                (team.id, team.name, team.personnel_count),
            )

    def assign_tracker(self, assignment: TrackerAssignment) -> None:
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
                    assignment.unassigned_at.isoformat() if assignment.unassigned_at else None,
                ),
            )

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

    