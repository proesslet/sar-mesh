from pathlib import Path

from sarmesh.core.registry import TrackerRegistry
from sarmesh.services.tracking import TrackingService
from sarmesh.storage.database import Database
from sarmesh.transports.meshtastic import MeshtasticTransport


def main() -> None:
    database = Database(Path("sarmesh.db"))
    database.initialize()

    registry = TrackerRegistry()

    tracking_service = TrackingService(registry=registry, database=database)

    transport = MeshtasticTransport(on_position=tracking_service.handle_position)
    transport.run()
