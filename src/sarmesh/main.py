from datetime import datetime, timezone

from sarmesh.transports.meshtastic import MeshtasticTransport
from sarmesh.core.registry import TrackerRegistry
from sarmesh.storage.database import Database
from sarmesh.services.tracking import TrackingService
from sarmesh.core.models import Incident



def main() -> None:
    database = Database("sarmesh.db")
    database.initialize()


    registry = TrackerRegistry()
    
    tracking_service = TrackingService(registry=registry, database=database)

    transport = MeshtasticTransport(on_position=tracking_service.handle_position)
    transport.run()
