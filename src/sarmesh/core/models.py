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


@dataclass
class TrackerStatus:
    tracker: Tracker
    team: Team | None
    position: TrackerPosition | None
    last_seen_at: datetime | None


@dataclass
class RadioInfo:
    """The attached node's own identity, as the interface already knows it.

    Read from the config the library downloads when it connects, so this costs
    no airtime and answers even when nothing else is in range. Every field is
    optional because a node that connected but has not finished its config
    download reports part of this and nothing else.
    """

    node_id: str | None
    node_num: int | None
    long_name: str | None
    short_name: str | None
    hardware: str | None
    firmware_version: str | None
    role: str | None
    # Nodes in the attached node's local database, including itself.
    node_count: int
