"""Request and response models for the HTTP API.

Response models carry `from_attributes` so they validate straight off the
dataclasses in core.models, and Pydantic serialises their datetimes as
ISO-8601. Field names are snake_case to match the wire format the frontend
already consumes.

The basemap routes are the exception: they still return plain dicts, since
their payloads are assembled from MBTiles metadata rather than a model.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sarmesh.services.basemaps import Bounds

########################## Incidents ##########################


class IncidentCreate(BaseModel):
    name: str = Field(min_length=1)


class IncidentUpdate(BaseModel):
    name: str = Field(min_length=1)


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    started_at: datetime
    ended_at: datetime | None


########################## Teams ##########################


class TeamCreate(BaseModel):
    name: str = Field(min_length=1)
    personnel_count: int = Field(default=1, ge=0)


class TeamUpdate(BaseModel):
    """A partial edit. Omitted fields are left alone rather than reset."""

    name: str | None = Field(default=None, min_length=1)
    personnel_count: int | None = Field(default=None, ge=0)


class TeamBase(BaseModel):
    """A team on its own, as it appears nested inside a tracker status."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    personnel_count: int


class TeamOut(TeamBase):
    # Trackers currently held. Carried alongside the team rather than looked up
    # separately, because it is what explains why a team cannot be deleted.
    tracker_count: int = 0


########################## Trackers ##########################


class TrackerCreate(BaseModel):
    node_id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class TrackerUpdate(BaseModel):
    # Only the label is editable. A node id identifies a physical radio, so
    # changing it would silently orphan every position already recorded.
    label: str = Field(min_length=1)


class TrackerBase(BaseModel):
    """A tracker record on its own, without the assignment lookup."""

    model_config = ConfigDict(from_attributes=True)

    node_id: str
    label: str


class AssignmentSummary(BaseModel):
    """Who is holding a tracker, named rather than left as bare ids.

    This is what stops a tracker being deleted, so the operator has to be told
    which team and incident are involved.
    """

    incident_id: str
    incident_name: str | None
    team_id: str
    team_name: str | None


class TrackerOut(TrackerBase):
    # Non-null while a team is carrying it, which is what blocks deletion.
    assignment: AssignmentSummary | None = None


class UnregisteredNodeOut(BaseModel):
    """A node heard on the mesh that has no tracker record yet."""

    node_id: str
    node_num: int
    last_seen_at: datetime


########################## Assignments ##########################


class AssignmentCreate(BaseModel):
    incident_id: str = Field(min_length=1)
    tracker_node_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: str
    tracker_node_id: str
    team_id: str
    assigned_at: datetime
    unassigned_at: datetime | None


########################## Live status ##########################


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: str
    node_num: int
    latitude: float
    longitude: float
    received_at: datetime
    satellites: int | None
    precision_bits: int | None
    rssi: int | None
    snr: float | None


class TrackerStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tracker: TrackerBase
    team: TeamBase | None
    position: PositionOut | None
    last_seen_at: datetime | None


########################## Basemaps ##########################


class BasemapSelect(BaseModel):
    # None turns the basemap off, which is a legitimate choice: positions still
    # plot without one, and a wrong pack is worse than no pack.
    name: str | None = None


class OnlineSource(BaseModel):
    url_template: str = Field(min_length=1)
    enabled: bool


class BasemapArea(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    min_zoom: int = Field(ge=0, le=22)
    max_zoom: int = Field(ge=0, le=22)

    def bounds(self) -> Bounds:
        return Bounds(
            west=self.west, south=self.south, east=self.east, north=self.north
        ).normalised()


class BasemapDownload(BasemapArea):
    name: str = Field(min_length=1)
    # The tile server to fetch from. Supplied by the operator because no source
    # can be assumed to permit bulk downloading on a search team's behalf.
    url_template: str = Field(min_length=1)


########################## Diagnostics ##########################


class FileLocationOut(BaseModel):
    path: str
    exists: bool
    size_bytes: int | None


class DiagnosticsOut(BaseModel):
    frozen: bool
    data_dir: str
    database: FileLocationOut
    log: FileLocationOut
    basemap_dir: FileLocationOut | None


class LogTailOut(BaseModel):
    path: str
    exists: bool
    lines: list[str]
