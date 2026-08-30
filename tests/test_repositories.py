"""Single-table queries, and the assignment history they depend on."""

from datetime import UTC, datetime, timedelta, timezone

from conftest import make_position

from sarmesh.storage.database import Database

########################## Incidents ##########################


def test_create_incident_returns_an_open_incident(database: Database) -> None:
    incident = database.incidents.create("Ridgeline")

    assert incident.ended_at is None
    assert database.incidents.get(incident.id) == incident


def test_get_unknown_incident_is_none(database: Database) -> None:
    assert database.incidents.get("nope") is None


def test_active_is_none_when_every_incident_has_ended(database: Database) -> None:
    incident = database.incidents.create("Ridgeline")
    database.incidents.end(incident.id, ended_at=datetime.now(UTC))

    assert database.incidents.active() is None


def test_update_incident_renames_it(database: Database) -> None:
    incident = database.incidents.create("Ridgeline")

    updated = database.incidents.update(incident.id, name="Ridgeline North")

    assert updated is not None
    assert updated.name == "Ridgeline North"
    assert updated.started_at == incident.started_at


########################## Teams ##########################


def test_update_team_leaves_omitted_fields_alone(database: Database) -> None:
    team = database.teams.create("Alpha", personnel_count=4)

    renamed = database.teams.update(team.id, name="Bravo")

    assert renamed is not None
    assert renamed.name == "Bravo"
    assert renamed.personnel_count == 4


def test_update_team_accepts_a_zero_personnel_count(database: Database) -> None:
    """0 is a real value, not "omitted": the guard is `is not None`."""
    team = database.teams.create("Alpha", personnel_count=4)

    updated = database.teams.update(team.id, personnel_count=0)

    assert updated is not None
    assert updated.personnel_count == 0


def test_teams_are_listed_by_name(database: Database) -> None:
    database.teams.create("Charlie", personnel_count=1)
    database.teams.create("Alpha", personnel_count=1)
    database.teams.create("Bravo", personnel_count=1)

    assert [team.name for team in database.teams.list()] == [
        "Alpha",
        "Bravo",
        "Charlie",
    ]


########################## Trackers ##########################


def test_tracker_round_trips(database: Database) -> None:
    tracker = database.trackers.create("!aabbccdd", "Alpha 1")

    assert database.trackers.get("!aabbccdd") == tracker


def test_delete_tracker_removes_it(database: Database) -> None:
    database.trackers.create("!aabbccdd", "Alpha 1")

    database.trackers.delete("!aabbccdd")

    assert database.trackers.get("!aabbccdd") is None
    assert database.trackers.list() == []


########################## Assignments ##########################


def test_active_for_is_none_before_assignment(database: Database) -> None:
    assert database.assignments.active_for("!aabbccdd") is None


def test_assignment_becomes_active(database: Database) -> None:
    assignment = database.assignments.create("inc", "!aabbccdd", "team")

    active = database.assignments.active_for("!aabbccdd")

    assert active is not None
    assert active.incident_id == "inc"
    assert active.team_id == "team"
    assert active.unassigned_at is None
    assert active.assigned_at == assignment.assigned_at


def test_release_stamps_rather_than_deletes(database: Database) -> None:
    """An incident's attribution has to be reconstructable afterwards."""
    database.assignments.create("inc", "!aabbccdd", "team")
    released_at = datetime.now(UTC)

    database.assignments.release("!aabbccdd", unassigned_at=released_at)

    assert database.assignments.active_for("!aabbccdd") is None

    with database.transaction() as connection:
        rows = connection.execute("SELECT * FROM tracker_assignments").fetchall()

    assert len(rows) == 1
    assert rows[0]["unassigned_at"] == released_at.isoformat()


def test_a_released_tracker_can_be_reassigned(database: Database) -> None:
    database.assignments.create("inc", "!aabbccdd", "alpha")
    database.assignments.release("!aabbccdd", unassigned_at=datetime.now(UTC))

    database.assignments.create("inc", "!aabbccdd", "bravo")

    active = database.assignments.active_for("!aabbccdd")
    assert active is not None
    assert active.team_id == "bravo"


def test_active_for_incident_ignores_other_incidents(database: Database) -> None:
    database.assignments.create("inc-1", "!aaaa", "alpha")
    database.assignments.create("inc-2", "!bbbb", "bravo")

    assignments = database.assignments.active_for_incident("inc-1")

    assert [a.tracker_node_id for a in assignments] == ["!aaaa"]


def test_list_active_spans_incidents_but_not_released(database: Database) -> None:
    database.assignments.create("inc-1", "!aaaa", "alpha")
    database.assignments.create("inc-2", "!bbbb", "bravo")
    database.assignments.create("inc-2", "!cccc", "bravo")
    database.assignments.release("!cccc", unassigned_at=datetime.now(UTC))

    assert {a.tracker_node_id for a in database.assignments.list_active()} == {
        "!aaaa",
        "!bbbb",
    }


def test_release_of_an_unassigned_tracker_is_a_no_op(database: Database) -> None:
    database.assignments.release("!aabbccdd", unassigned_at=datetime.now(UTC))

    assert database.assignments.list_active() == []


########################## Positions ##########################


def test_save_position_stamps_the_incident(database: Database) -> None:
    database.positions.save(make_position(), incident_id="inc")

    assert database.positions.latest_for_node("!aabbccdd", "inc") is not None


def test_position_round_trips_every_field(database: Database) -> None:
    original = make_position(satellites=7, precision_bits=16, rssi=-101, snr=-2.5)

    database.positions.save(original, incident_id="inc")

    stored = database.positions.latest_for_node("!aabbccdd", "inc")
    assert stored == original


def test_latest_for_node_is_scoped_to_the_incident(database: Database) -> None:
    """A previous search's positions must not leak into the current one."""
    database.positions.save(make_position(latitude=1.0), incident_id="old")
    database.positions.save(make_position(latitude=2.0), incident_id="current")

    stored = database.positions.latest_for_node("!aabbccdd", "current")

    assert stored is not None
    assert stored.latitude == 2.0


def test_latest_for_node_returns_the_newest(database: Database) -> None:
    base = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    database.positions.save(
        make_position(latitude=1.0, received_at=base), incident_id="inc"
    )
    database.positions.save(
        make_position(latitude=2.0, received_at=base + timedelta(minutes=5)),
        incident_id="inc",
    )

    stored = database.positions.latest_for_node("!aabbccdd", "inc")

    assert stored is not None
    assert stored.latitude == 2.0


def test_unassigned_positions_are_kept(database: Database) -> None:
    """A node with no assignment still beacons, and the data is still worth
    having; it just is not attributed to a search."""
    database.positions.save(make_position(), incident_id=None)

    latest = database.positions.latest_per_node()

    assert [position.node_id for position in latest] == ["!aabbccdd"]


def test_latest_per_node_returns_one_row_per_node(database: Database) -> None:
    database.positions.save(make_position("!aaaa", latitude=1.0), incident_id=None)
    database.positions.save(make_position("!aaaa", latitude=2.0), incident_id=None)
    database.positions.save(make_position("!bbbb"), incident_id=None)

    latest = {p.node_id: p for p in database.positions.latest_per_node()}

    assert set(latest) == {"!aaaa", "!bbbb"}
    assert latest["!aaaa"].latitude == 2.0


def test_latest_per_node_breaks_same_second_ties_by_id(database: Database) -> None:
    """rxTime is whole seconds, so two beacons can share a timestamp."""
    same_second = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    database.positions.save(
        make_position(latitude=1.0, received_at=same_second), incident_id=None
    )
    database.positions.save(
        make_position(latitude=2.0, received_at=same_second), incident_id=None
    )

    latest = database.positions.latest_per_node()

    assert len(latest) == 1
    assert latest[0].latitude == 2.0


def test_latest_per_node_can_be_bounded_by_since(database: Database) -> None:
    """A laptop reused across searches must not report last month's positions
    as nodes standing still on this one."""
    base = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    database.positions.save(
        make_position("!old", received_at=base - timedelta(days=30)), incident_id=None
    )
    database.positions.save(make_position("!now", received_at=base), incident_id=None)

    latest = database.positions.latest_per_node(since=base - timedelta(hours=1))

    assert [position.node_id for position in latest] == ["!now"]


########################## Position history ##########################


def _save_walk(
    database: Database,
    node_id: str,
    count: int,
    *,
    incident_id: str | None = "inc",
    start: datetime | None = None,
) -> None:
    """`count` beacons a minute apart, latitudes counting up from 1."""
    base = start or datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

    for step in range(count):
        database.positions.save(
            make_position(
                node_id,
                latitude=float(step + 1),
                received_at=base + timedelta(minutes=step),
            ),
            incident_id=incident_id,
        )


def test_history_groups_positions_by_node(database: Database) -> None:
    _save_walk(database, "!aaaa", 3)
    _save_walk(database, "!bbbb", 2)

    tracks = database.positions.history_for_incident("inc")

    assert {node: len(points) for node, points in tracks.items()} == {
        "!aaaa": 3,
        "!bbbb": 2,
    }


def test_history_is_oldest_first(database: Database) -> None:
    """The polyline is drawn in array order, so a reversed track draws the
    trail backwards from where the tracker actually walked."""
    _save_walk(database, "!aaaa", 4)

    [*points] = database.positions.history_for_incident("inc")["!aaaa"]

    assert [point.latitude for point in points] == [1.0, 2.0, 3.0, 4.0]


def test_history_caps_each_node_separately(database: Database) -> None:
    """One chatty radio must not crowd the rest of the search out of the
    answer, which a single overall LIMIT would let it do."""
    _save_walk(database, "!chatty", 5)
    _save_walk(database, "!quiet", 5)

    tracks = database.positions.history_for_incident("inc", limit_per_node=2)

    assert {node: len(points) for node, points in tracks.items()} == {
        "!chatty": 2,
        "!quiet": 2,
    }


def test_history_keeps_the_newest_fixes_when_capped(database: Database) -> None:
    """Trimming the old end shortens the trail; trimming the new end would
    leave the tracker drawn somewhere it has already left."""
    _save_walk(database, "!aaaa", 5)

    points = database.positions.history_for_incident("inc", limit_per_node=2)["!aaaa"]

    assert [point.latitude for point in points] == [4.0, 5.0]


def test_history_breaks_a_same_second_tie_by_id(database: Database) -> None:
    """rxTime is whole seconds, so the cap boundary would otherwise fall
    somewhere different on each call."""
    same_second = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

    for latitude in (1.0, 2.0, 3.0):
        database.positions.save(
            make_position(latitude=latitude, received_at=same_second),
            incident_id="inc",
        )

    points = database.positions.history_for_incident("inc", limit_per_node=2)

    assert [point.latitude for point in points["!aabbccdd"]] == [2.0, 3.0]


def test_history_excludes_another_incident(database: Database) -> None:
    _save_walk(database, "!aaaa", 2, incident_id="old")
    _save_walk(database, "!aaaa", 3, incident_id="current")

    tracks = database.positions.history_for_incident("current")

    assert len(tracks["!aaaa"]) == 3


def test_history_excludes_unattributed_positions(database: Database) -> None:
    """A node beaconing while unassigned is stored with no incident, and has
    no trail on anyone's search."""
    _save_walk(database, "!aaaa", 2, incident_id=None)

    assert database.positions.history_for_incident("inc") == {}


def test_history_without_a_since_returns_everything(database: Database) -> None:
    _save_walk(database, "!aaaa", 3)

    assert len(database.positions.history_for_incident("inc")["!aaaa"]) == 3


def test_history_since_drops_earlier_fixes(database: Database) -> None:
    base = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    _save_walk(database, "!aaaa", 5, start=base)

    points = database.positions.history_for_incident(
        "inc", since=base + timedelta(minutes=3)
    )["!aaaa"]

    assert [point.latitude for point in points] == [4.0, 5.0]


def test_history_since_is_honoured_across_a_non_utc_offset(database: Database) -> None:
    """Timestamps are compared as text, so a +02:00 bound would sort after the
    same instant written as UTC and silently drop two hours of the trail."""
    base = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    _save_walk(database, "!aaaa", 5, start=base)

    shifted = (base + timedelta(minutes=3)).astimezone(timezone(timedelta(hours=2)))
    points = database.positions.history_for_incident("inc", since=shifted)["!aaaa"]

    assert [point.latitude for point in points] == [4.0, 5.0]


########################## Settings ##########################


def test_setting_round_trips(database: Database) -> None:
    database.settings.set("basemap", "terrain.mbtiles")

    assert database.settings.get("basemap") == "terrain.mbtiles"


def test_setting_overwrites_rather_than_conflicting(database: Database) -> None:
    database.settings.set("basemap", "one.mbtiles")
    database.settings.set("basemap", "two.mbtiles")

    assert database.settings.get("basemap") == "two.mbtiles"


def test_setting_none_clears_the_key(database: Database) -> None:
    database.settings.set("basemap", "terrain.mbtiles")

    database.settings.set("basemap", None)

    assert database.settings.get("basemap") is None


def test_unset_setting_is_none(database: Database) -> None:
    assert database.settings.get("basemap") is None
