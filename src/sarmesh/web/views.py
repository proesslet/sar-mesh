"""Read models: the shapes the UI asks for, built from several queries.

A tracker's assignment, a team's tracker count and a tracker's live status are
not fields on any row. Each is a small join, and assembling them here keeps the
route handlers to validation and the repositories to single-table SQL.
"""

from sarmesh.core.models import Team, Tracker
from sarmesh.storage.database import Database
from sarmesh.web.schemas import (
    AssignmentSummary,
    PositionOut,
    TeamBase,
    TeamOut,
    TrackerBase,
    TrackerOut,
    TrackerStatusOut,
)


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
