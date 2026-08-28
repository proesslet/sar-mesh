import asyncio
import threading
from dataclasses import asdict
from typing import Any

from sarmesh.core.models import TrackerPosition


class PositionBroadcaster:
    """Fans positions out from the radio thread to any number of SSE clients.

    Positions are published by the Meshtastic "publishing" thread, while
    subscribers live on the server's asyncio loop. Every hand-off therefore
    goes through call_soon_threadsafe -- asyncio.Queue is not itself thread
    safe, so publishing into one directly would corrupt it under load.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        # Bounded so a stalled client cannot grow without limit; when it fills,
        # its oldest positions are dropped rather than stalling the radio.
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)

        with self._lock:
            self._subscribers.add(queue)

        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def publish(self, position: TrackerPosition) -> None:
        """Called from the radio thread."""
        with self._lock:
            loop = self._loop
            subscribers = list(self._subscribers)

        if loop is None or not subscribers:
            return

        payload = asdict(position)
        payload["received_at"] = position.received_at.isoformat()

        for queue in subscribers:
            loop.call_soon_threadsafe(self._offer, queue, payload)

    @staticmethod
    def _offer(queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
        # Runs on the loop thread, so touching the queue is safe here.
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass
