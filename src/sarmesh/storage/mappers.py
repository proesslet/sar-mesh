"""sqlite3.Row to domain model. One mapper per entity, used by every query."""

import sqlite3
from datetime import datetime

from sarmesh.core.models import (
    Incident,
    Team,
    Tracker,
    TrackerAssignment,
    TrackerPosition,
)


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_time(value: str | None) -> datetime | None:
    return _time(value) if value else None


def incident(row: sqlite3.Row) -> Incident:
    return Incident(
        id=row["id"],
        name=row["name"],
        started_at=_time(row["started_at"]),
        ended_at=_optional_time(row["ended_at"]),
    )


def position(row: sqlite3.Row) -> TrackerPosition:
    return TrackerPosition(
        node_id=row["node_id"],
        node_num=row["node_num"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        received_at=_time(row["received_at"]),
        satellites=row["satellites"],
        precision_bits=row["precision_bits"],
        rssi=row["rssi"],
        snr=row["snr"],
    )


def tracker(row: sqlite3.Row) -> Tracker:
    return Tracker(node_id=row["node_id"], label=row["label"])


def team(row: sqlite3.Row) -> Team:
    return Team(
        id=row["id"],
        name=row["name"],
        personnel_count=row["personnel_count"],
    )


def assignment(row: sqlite3.Row) -> TrackerAssignment:
    return TrackerAssignment(
        incident_id=row["incident_id"],
        tracker_node_id=row["tracker_node_id"],
        team_id=row["team_id"],
        assigned_at=_time(row["assigned_at"]),
        unassigned_at=_optional_time(row["unassigned_at"]),
    )
