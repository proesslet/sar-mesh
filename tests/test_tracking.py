"""The ingest path: what happens to a position between radio and database."""

from datetime import UTC, datetime

from conftest import make_position

from sarmesh.core.models import TrackerPosition
from sarmesh.services.tracking import TrackingService
from sarmesh.storage.database import Database


class RecordingBroadcaster:
    """Stands in for PositionBroadcaster, which needs a running event loop."""

    def __init__(self, database: Database | None = None) -> None:
        self.published: list[TrackerPosition] = []
        # Set to assert ordering: what was already durable when we were called.
        self._database = database
        self.rows_at_publish: list[int] = []

    def publish(self, position: TrackerPosition) -> None:
        if self._database is not None:
            with self._database.transaction() as connection:
                count = connection.execute("SELECT COUNT(*) FROM positions").fetchone()[
                    0
                ]
            self.rows_at_publish.append(count)

        self.published.append(position)


def test_position_is_stamped_with_the_active_incident(database: Database) -> None:
    database.assignments.create("inc", "!aabbccdd", "alpha")
    service = TrackingService(database=database)

    service.handle_position(make_position())

    assert database.positions.latest_for_node("!aabbccdd", "inc") is not None


def test_unassigned_position_is_stored_without_an_incident(
    database: Database,
) -> None:
    service = TrackingService(database=database)

    service.handle_position(make_position())

    with database.transaction() as connection:
        row = connection.execute(
            "SELECT incident_id FROM positions WHERE node_id = ?", ("!aabbccdd",)
        ).fetchone()

    assert row["incident_id"] is None


def test_a_released_tracker_stops_being_attributed(database: Database) -> None:
    """The bug this guards: positions still landing on a closed search."""
    database.assignments.create("inc", "!aabbccdd", "alpha")
    service = TrackingService(database=database)
    service.handle_position(make_position(latitude=1.0))

    database.assignments.release("!aabbccdd", unassigned_at=datetime.now(UTC))
    service.handle_position(make_position(latitude=2.0))

    stored = database.positions.latest_for_node("!aabbccdd", "inc")
    assert stored is not None
    assert stored.latitude == 1.0


def test_a_reassigned_tracker_follows_the_new_incident(database: Database) -> None:
    service = TrackingService(database=database)
    database.assignments.create("inc-1", "!aabbccdd", "alpha")
    service.handle_position(make_position(latitude=1.0))

    database.assignments.release("!aabbccdd", unassigned_at=datetime.now(UTC))
    database.assignments.create("inc-2", "!aabbccdd", "bravo")
    service.handle_position(make_position(latitude=2.0))

    first = database.positions.latest_for_node("!aabbccdd", "inc-1")
    second = database.positions.latest_for_node("!aabbccdd", "inc-2")

    assert first is not None and first.latitude == 1.0
    assert second is not None and second.latitude == 2.0


def test_position_is_broadcast(database: Database) -> None:
    broadcaster = RecordingBroadcaster()
    service = TrackingService(database=database, broadcaster=broadcaster)  # type: ignore[arg-type]

    position = make_position()
    service.handle_position(position)

    assert broadcaster.published == [position]


def test_position_is_durable_before_it_is_broadcast(database: Database) -> None:
    """The UI must never be told about something a crash could still lose."""
    broadcaster = RecordingBroadcaster(database)
    service = TrackingService(database=database, broadcaster=broadcaster)  # type: ignore[arg-type]

    service.handle_position(make_position())

    assert broadcaster.rows_at_publish == [1]


def test_handle_position_works_without_a_broadcaster(database: Database) -> None:
    """The `sarmesh run` CLI has no broadcaster at all."""
    service = TrackingService(database=database)

    service.handle_position(make_position(received_at=datetime.now(UTC)))

    assert len(database.positions.latest_per_node()) == 1
