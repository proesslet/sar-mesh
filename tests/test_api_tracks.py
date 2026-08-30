"""/api/tracks -- the trail the map draws behind each tracker.

A wrong answer here is a path a team never walked, which is worse than no path
at all: it is the kind of thing that sends someone to re-search ground that was
never covered.
"""

from datetime import UTC, datetime, timedelta, timezone

from conftest import make_position
from fastapi.testclient import TestClient

from sarmesh.storage.database import Database

BASE = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def walk(
    database: Database,
    node_id: str,
    incident_id: str,
    count: int,
    start: datetime = BASE,
) -> None:
    """`count` beacons a minute apart, latitudes counting up from 1."""
    for step in range(count):
        database.positions.save(
            make_position(
                node_id,
                latitude=float(step + 1),
                received_at=start + timedelta(minutes=step),
            ),
            incident_id=incident_id,
        )


def incident_of(database: Database, node_id: str) -> str:
    assignment = database.assignments.active_for(node_id)
    assert assignment is not None

    return assignment.incident_id


def test_tracks_are_empty_with_no_active_incident(client: TestClient) -> None:
    response = client.get("/api/tracks")

    assert response.status_code == 200
    assert response.json() == []


def test_tracks_default_to_the_active_incident(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 3)

    [track] = client.get("/api/tracks").json()

    assert track["node_id"] == assigned_tracker
    assert len(track["points"]) == 3


def test_a_track_is_ordered_oldest_first(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """The polyline is drawn in array order, so a reversed track would draw the
    trail running backwards from where the tracker actually walked."""
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 4)

    [track] = client.get("/api/tracks").json()

    assert [point["latitude"] for point in track["points"]] == [1.0, 2.0, 3.0, 4.0]


def test_a_track_point_carries_only_what_the_map_draws(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """This is the largest response the API sends. Signal strength and
    satellite counts are read one pin at a time, never along a trail."""
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 1)

    [track] = client.get("/api/tracks").json()

    assert set(track["points"][0]) == {"latitude", "longitude", "received_at"}


def test_tracks_exclude_another_incidents_positions(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """The previous search's trail must not be drawn as this one's."""
    walk(database, assigned_tracker, "an-older-search", 5)
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 2)

    [track] = client.get("/api/tracks").json()

    assert len(track["points"]) == 2


def test_tracks_exclude_a_tracker_not_on_this_incident(
    client: TestClient, database: Database, incident_id: str, node_id: str
) -> None:
    """Positions recorded under this incident but for a tracker nobody is
    carrying belong to no team, so there is no trail to attribute."""
    walk(database, node_id, incident_id, 3)

    assert client.get("/api/tracks").json() == []


def test_a_tracker_that_has_not_beaconed_has_no_track(
    client: TestClient, assigned_tracker: str
) -> None:
    """An empty trail is only something for the caller to filter out again."""
    assert client.get("/api/tracks").json() == []


def test_since_drops_fixes_from_before_the_window(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 5)

    since = (BASE + timedelta(minutes=3)).isoformat()
    [track] = client.get("/api/tracks", params={"since": since}).json()

    assert [point["latitude"] for point in track["points"]] == [4.0, 5.0]


def test_since_is_honoured_across_a_non_utc_offset(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """Timestamps are compared as text, so a +02:00 bound would sort after the
    same instant written as UTC and silently cut two hours off the trail."""
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 5)

    shifted = (BASE + timedelta(minutes=3)).astimezone(timezone(timedelta(hours=2)))
    [track] = client.get("/api/tracks", params={"since": shifted.isoformat()}).json()

    assert [point["latitude"] for point in track["points"]] == [4.0, 5.0]


def test_a_capped_track_keeps_the_newest_fixes(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    """Trimming the old end shortens the trail; trimming the new end would
    leave the tracker drawn somewhere it had already left."""
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 5)

    [track] = client.get("/api/tracks", params={"limit": 2}).json()

    assert [point["latitude"] for point in track["points"]] == [4.0, 5.0]
    assert track["truncated"] is True


def test_a_short_track_is_not_reported_as_truncated(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    walk(database, assigned_tracker, incident_of(database, assigned_tracker), 2)

    [track] = client.get("/api/tracks", params={"limit": 10}).json()

    assert track["truncated"] is False


def test_tracks_reject_a_zero_limit(client: TestClient) -> None:
    assert client.get("/api/tracks", params={"limit": 0}).status_code == 422
