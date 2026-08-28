from sarmesh.core.events import PositionBroadcaster
from sarmesh.core.models import TrackerPosition
from sarmesh.storage.database import Database


class TrackingService:
    """Records positions as they arrive from the radio"""

    def __init__(
        self,
        database: Database,
        broadcaster: PositionBroadcaster | None = None,
    ) -> None:
        self.database = database
        self.broadcaster = broadcaster

    def handle_position(self, position: TrackerPosition) -> None:

        assignment = self.database.get_active_assignment(position.node_id)

        incident_id = None

        if assignment is not None:
            incident_id = assignment.incident_id

        self.database.save_position(
            position,
            incident_id=incident_id,
        )

        # Persist before broadcasting, so anything the UI is told about is
        # already durable.
        if self.broadcaster is not None:
            self.broadcaster.publish(position)
