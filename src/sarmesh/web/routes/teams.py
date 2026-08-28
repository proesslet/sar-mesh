import logging

from fastapi import APIRouter, HTTPException

from sarmesh.web import views
from sarmesh.web.dependencies import Db
from sarmesh.web.schemas import TeamCreate, TeamOut, TeamUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("")
def list_teams(database: Db) -> list[TeamOut]:
    return views.list_teams(database)


@router.post("", status_code=201)
def create_team(body: TeamCreate, database: Db) -> TeamOut:
    team = database.teams.create(
        name=body.name,
        personnel_count=body.personnel_count,
    )

    return views.describe_team(team, {})


@router.delete("/{team_id}")
def delete_team(team_id: str, database: Db) -> list[TeamOut]:
    """Remove a team, unless it is currently holding trackers.

    Returns the remaining teams rather than an empty 204, so the caller cannot
    show a list that disagrees with the database.
    """
    team = database.teams.get(team_id)

    if team is None:
        raise HTTPException(404, f"No team {team_id}")

    held = [
        a.tracker_node_id
        for a in database.assignments.list_active()
        if a.team_id == team_id
    ]

    if held:
        raise HTTPException(
            409,
            f"{team.name} still has {len(held)} tracker(s) assigned. "
            "Unassign them first, or their positions stop being attributed "
            "to anyone.",
        )

    database.teams.delete(team_id)
    logger.info("Deleted team %s (%s)", team.name, team_id)

    return views.list_teams(database)


@router.patch("/{team_id}")
def update_team(team_id: str, body: TeamUpdate, database: Db) -> TeamOut:
    if database.teams.get(team_id) is None:
        raise HTTPException(404, f"No team {team_id}")

    updated = database.teams.update(
        team_id,
        name=body.name,
        personnel_count=body.personnel_count,
    )

    if updated is None:
        raise HTTPException(404, f"No team {team_id}")

    # A team being renamed may still be holding trackers, so the count has to
    # be looked up rather than assumed empty.
    return views.describe_team(updated, views.assignment_counts(database))
