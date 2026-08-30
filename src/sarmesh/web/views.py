"""Read models: the shapes the UI asks for, built from several queries.

A tracker's assignment, a team's tracker count and a tracker's live status are
not fields on any row. Each is a small join, and assembling them here keeps the
route handlers to validation and the repositories to single-table SQL.
"""

from datetime import datetime, timedelta

from sarmesh.core.models import Team, Tracker
from sarmesh.storage.database import Database
from sarmesh.storage.repositories.positions import MAX_TRACK_POINTS
from sarmesh.web.schemas import (
    AssignmentSummary,
    NodeOut,
    PositionOut,
    TeamBase,
    TeamOut,
    TrackerBase,
    TrackerOut,
    TrackerStatusOut,
    TrackOut,
    TrackPointOut,
)

# How far before an incident opened a node can have been heard and still count
# as out there. Generous next to a Meshtastic beacon interval of a few minutes,
# so a node stays visible while the operator is still filling in the form.
HEARD_BEFORE_START = timedelta(hours=1)


def resolve_incident(database: Database, incident_id: str | None) -> str | None:
    """The incident a request is about: the one asked for, or the open one.

    Returns None when nothing is running, which every caller renders as an
    empty answer rather than an error -- a base station with no incident open
    is a normal state, not a failure.
    """
    if incident_id is not None:
        return incident_id

    incident = database.incidents.active()

    return incident.id if incident else None


def assignment_counts(database: Database) -> dict[str, int]:
    """How many trackers each team is currently holding, keyed by team id."""
    counts: dict[str, int] = {}

    for assignment in database.assignments.list_active():
        counts[assignment.team_id] = counts.get(assignment.team_id, 0) + 1

    return counts


def describe_team(team: Team, counts: dict[str, int]) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        personnel_count=team.personnel_count,
        tracker_count=counts.get(team.id, 0),
    )


def list_teams(database: Database) -> list[TeamOut]:
    # Counted once for the whole list, not per team.
    counts = assignment_counts(database)

    return [describe_team(team, counts) for team in database.teams.list()]


def describe_tracker(database: Database, tracker: Tracker) -> TrackerOut:
    assignment = database.assignments.active_for(tracker.node_id)

    if assignment is None:
        return TrackerOut(node_id=tracker.node_id, label=tracker.label)

    team = database.teams.get(assignment.team_id)
    incident = database.incidents.get(assignment.incident_id)

    return TrackerOut(
        node_id=tracker.node_id,
        label=tracker.label,
        assignment=AssignmentSummary(
            incident_id=assignment.incident_id,
            incident_name=incident.name if incident else None,
            team_id=assignment.team_id,
            team_name=team.name if team else None,
        ),
    )


def list_trackers(database: Database) -> list[TrackerOut]:
    # Three queries per tracker. Fine at field scale, where a search runs tens
    # of trackers against a local SQLite file.
    return [describe_tracker(database, t) for t in database.trackers.list()]


def list_statuses(database: Database, incident_id: str) -> list[TrackerStatusOut]:
    """Every tracker working an incident, with its team and last position.

    This is what the map draws. Trackers assigned to a different incident are
    absent rather than unassigned, since they are not part of this search.
    """
    statuses = []

    for assignment in database.assignments.active_for_incident(incident_id):
        tracker = database.trackers.get(assignment.tracker_node_id)

        # The CLI can assign a node id that was never registered, so a missing
        # tracker here is a real possibility rather than a can't-happen.
        if tracker is None:
            continue

        position = database.positions.latest_for_node(tracker.node_id, incident_id)

        team = database.teams.get(assignment.team_id)

        statuses.append(
            TrackerStatusOut(
                tracker=TrackerBase.model_validate(tracker),
                team=TeamBase.model_validate(team) if team else None,
                position=PositionOut.model_validate(position) if position else None,
                last_seen_at=position.received_at if position else None,
            )
        )

    return statuses


def list_nodes(database: Database, incident_id: str) -> list[NodeOut]:
    """Every node heard on the mesh around and during this incident.

    Wider than list_statuses on purpose: this is what lets an operator see a
    node that is beaconing but has not been given to a team yet, which is the
    thing they need in order to assign it.

    Bounded because positions are never pruned -- a laptop reused across
    searches would otherwise show months of stale nodes, every one of them
    looking like somebody standing still. The grace period before the start is
    what keeps a node that beaconed while the operator was still typing the
    incident name from being invisible until its next beacon.
    """
    incident = database.incidents.get(incident_id)

    if incident is None:
        return []

    labels = {tracker.node_id: tracker.label for tracker in database.trackers.list()}

    teams: dict[str, TeamBase] = {}

    for assignment in database.assignments.active_for_incident(incident_id):
        team = database.teams.get(assignment.team_id)

        if team is not None:
            teams[assignment.tracker_node_id] = TeamBase.model_validate(team)

    return [
        NodeOut(
            node_id=position.node_id,
            node_num=position.node_num,
            label=labels.get(position.node_id),
            team=teams.get(position.node_id),
            position=PositionOut.model_validate(position),
        )
        for position in database.positions.latest_per_node(
            since=incident.started_at - HEARD_BEFORE_START
        )
    ]


def list_tracks(
    database: Database,
    incident_id: str,
    since: datetime | None = None,
    limit: int = MAX_TRACK_POINTS,
) -> list[TrackOut]:
    """The path each tracker has walked during one incident.

    Restricted to the trackers list_statuses is showing, so the map can never
    draw a trail belonging to nobody. Positions were stamped with the incident
    they were recorded under, so a tracker released mid-search keeps the trail
    it earned rather than losing it retroactively.

    Trackers that have not beaconed are absent rather than present and empty:
    there is no trail to draw, and an empty one would only be something for the
    caller to filter out again.
    """
    tracks = database.positions.history_for_incident(
        incident_id, since=since, limit_per_node=limit
    )

    return [
        TrackOut(
            node_id=assignment.tracker_node_id,
            truncated=len(points) >= limit,
            points=[TrackPointOut.model_validate(point) for point in points],
        )
        for assignment in database.assignments.active_for_incident(incident_id)
        if (points := tracks.get(assignment.tracker_node_id))
    ]
