from sarmesh.core.models import TrackerPosition
from sarmesh.core.registry import TrackerRegistry
from sarmesh.storage.database import Database


class TrackingService:
    def __init__(
        self,
        registry: TrackerRegistry,
        database: Database,
    ) -> None:
        self.registry = registry
        self.database = database

    def handle_position(self, position: TrackerPosition) -> None:
        self.registry.update(position)

        assignment = self.database.get_active_assignment(
            position.node_id
        )

        incident_id = None

        if assignment is not None:
            incident_id = assignment.incident_id

        self.database.save_position(
            position,
            incident_id=incident_id,
        )