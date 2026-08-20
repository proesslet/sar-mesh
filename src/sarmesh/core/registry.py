from sarmesh.core.models import TrackerPosition


class TrackerRegistry:
    def __init__(self) -> None:
        self._positions: dict[str, TrackerPosition] = {}

    def update(self, position: TrackerPosition) -> None:
        self._positions[position.node_id] = position

    def get(self, node_id: str) -> TrackerPosition | None:
        return self._positions.get(node_id)

    def all(self) -> list[TrackerPosition]:
        return list(self._positions.values())