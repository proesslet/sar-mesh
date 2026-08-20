from sarmesh.transports.meshtastic import MeshtasticTransport
from sarmesh.core.registry import TrackerRegistry
from sarmesh.storage.database import Database



def main() -> None:
    registry = TrackerRegistry()
    database = Database("positions.db")
    database.initialize()

    def handle_position(position) -> None:
        registry.update(position)
        database.save_position(position)


        print("\nKnown Trackers:")
        for tracker in registry.all():
            print(
                tracker.node_id,
                tracker.latitude,
                tracker.longitude,
                tracker.received_at,
            )

    transport = MeshtasticTransport(handle_position)
    transport.run()