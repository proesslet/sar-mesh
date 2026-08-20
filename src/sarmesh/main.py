from sarmesh.transports.meshtastic import MeshtasticTransport
from sarmesh.core.registry import TrackerRegistry



def main() -> None:
    registry = TrackerRegistry()

    def handle_position(position) -> None:
        registry.update(position)

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