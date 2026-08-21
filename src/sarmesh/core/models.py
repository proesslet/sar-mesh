from dataclasses import dataclass
from datetime import datetime

@dataclass
class TrackerPosition:
    node_id: str
    node_num: int
    latitude: float
    longitude: float
    received_at: datetime

    satellites: int | None = None
    precision_bits: int | None = None
    rssi: int | None = None
    snr: float | None = None

@dataclass
class Incident:
    id: str
    name: str
    started_at: datetime
    ended_at: datetime | None = None

@dataclass
class Tracker:
    node_id: str
    label: str


@dataclass
class Team:
    id: str
    name: str
    personnel_count: int


@dataclass
class TrackerAssignment:
    incident_id: str
    tracker_node_id: str
    team_id: str
    assigned_at: datetime
    unassigned_at: datetime | None = None