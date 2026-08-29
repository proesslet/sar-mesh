"""/api/status -- the snapshot the map draws on load.

This is the closest thing to "what the operator actually sees", so the cases
here are the ones where a wrong answer is a person shown in the wrong place.
"""

from datetime import UTC, datetime, timedelta

from conftest import make_position
from fastapi.testclient import TestClient

from sarmesh.storage.database import Database


def test_status_is_empty_with_no_active_incident(client: TestClient) -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == []


def test_status_defaults_to_the_active_incident(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    database.positions.save(
        make_position(assigned_tracker),
        incident_id=database.assignments.active_for(assigned_tracker).incident_id,  # type: ignore[union-attr]
    )

    [status] = client.get("/api/status").json()

    assert status["tracker"]["node_id"] == assigned_tracker
    assert status["team"]["name"] == "Team Alpha"
    assert status["position"]["latitude"] == 44.4280
    assert status["last_seen_at"] == "2026-08-28T12:00:00Z"


def test_an_assigned_tracker_appears_before_it_beacons(
    client: TestClient, assigned_tracker: str
) -> None:
    """A team that has not been heard from yet is the thing an operator most
    needs to see, so it must not be filtered out for having no position."""
    [status] = client.get("/api/status").json()

    assert status["position"] is None
    assert status["last_seen_at"] is None


def test_status_excludes_trackers_on_another_incident(
    client: TestClient, team_id: str, node_id: str
) -> None:
    other = client.post("/api/incidents", json={"name": "Other"}).json()["id"]
    client.post(
        "/api/assignments",
        json={
            "incident_id": other,
            "tracker_node_id": node_id,
            "team_id": team_id,
        },
    )
    current = client.post("/api/incidents", json={"name": "Current"}).json()["id"]

    assert client.get(f"/api/status?incident_id={current}").json() == []


def test_status_excludes_unassigned_trackers(
    client: TestClient, incident_id: str, node_id: str
) -> None:
    assert client.get(f"/api/status?incident_id={incident_id}").json() == []


def test_position_is_scoped_to_the_incident(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """The previous search's last known position must not be shown as this
    search's, which would put a team somewhere they have never been."""
    current = database.assignments.active_for(assigned_tracker)
    assert current is not None
    database.positions.save(
        make_position(assigned_tracker, latitude=1.0), incident_id="an-old-search"
    )

    [status] = client.get("/api/status").json()

    assert status["position"] is None


def test_status_shows_the_newest_position(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    assignment = database.assignments.active_for(assigned_tracker)
    assert assignment is not None
    base = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

    for minutes, latitude in ((0, 1.0), (5, 2.0), (2, 1.5)):
        database.positions.save(
            make_position(
                assigned_tracker,
                latitude=latitude,
                received_at=base + timedelta(minutes=minutes),
            ),
            incident_id=assignment.incident_id,
        )

    [status] = client.get("/api/status").json()

    assert status["position"]["latitude"] == 2.0


def test_status_skips_an_assignment_with_no_tracker_record(
    client: TestClient, database: Database, incident_id: str, team_id: str
) -> None:
    """The CLI can assign a node id that was never registered."""
    database.assignments.create(incident_id, "!neverregistered", team_id)

    assert client.get("/api/status").json() == []


def test_status_survives_a_deleted_team(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """The API blocks this, but the CLI and a hand-edited database do not; the
    tracker still has to plot."""
    assignment = database.assignments.active_for(assigned_tracker)
    assert assignment is not None
    database.teams.delete(assignment.team_id)

    [status] = client.get("/api/status").json()

    assert status["team"] is None
    assert status["tracker"]["node_id"] == assigned_tracker
