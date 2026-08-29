"""Fanning positions from the radio thread out to SSE subscribers.

Every test drives the broadcaster the way the app does: publish() from a
non-loop thread, then let the loop run so the queued call_soon_threadsafe
callbacks land.
"""

import asyncio
import threading

import pytest
from conftest import make_position

from sarmesh.core.events import PositionBroadcaster


async def drain(queue: asyncio.Queue[dict[str, object]]) -> list[dict[str, object]]:
    """Everything currently queued, without blocking on an empty queue."""
    # One turn of the loop, so callbacks scheduled from another thread run.
    await asyncio.sleep(0)

    items = []
    while not queue.empty():
        items.append(queue.get_nowait())

    return items


def publish_off_loop(broadcaster: PositionBroadcaster, *positions: object) -> None:
    """Publish from another thread, as the Meshtastic reader does."""
    thread = threading.Thread(
        target=lambda: [broadcaster.publish(p) for p in positions]  # type: ignore[arg-type]
    )
    thread.start()
    thread.join()


@pytest.mark.anyio
async def test_a_subscriber_receives_a_published_position(
    broadcaster: PositionBroadcaster,
) -> None:
    broadcaster.bind_loop(asyncio.get_running_loop())
    queue = broadcaster.subscribe()

    publish_off_loop(broadcaster, make_position())

    assert [item["node_id"] for item in await drain(queue)] == ["!aabbccdd"]


@pytest.mark.anyio
async def test_received_at_is_serialised_as_iso_8601(
    broadcaster: PositionBroadcaster,
) -> None:
    """asdict() leaves a datetime in place, and json.dumps cannot encode one."""
    broadcaster.bind_loop(asyncio.get_running_loop())
    queue = broadcaster.subscribe()

    publish_off_loop(broadcaster, make_position())

    payload = (await drain(queue))[0]
    assert payload["received_at"] == "2026-08-28T12:00:00+00:00"


@pytest.mark.anyio
async def test_every_subscriber_gets_its_own_copy(
    broadcaster: PositionBroadcaster,
) -> None:
    broadcaster.bind_loop(asyncio.get_running_loop())
    first = broadcaster.subscribe()
    second = broadcaster.subscribe()

    publish_off_loop(broadcaster, make_position())

    assert len(await drain(first)) == 1
    assert len(await drain(second)) == 1


@pytest.mark.anyio
async def test_unsubscribe_stops_delivery(broadcaster: PositionBroadcaster) -> None:
    broadcaster.bind_loop(asyncio.get_running_loop())
    queue = broadcaster.subscribe()

    broadcaster.unsubscribe(queue)
    publish_off_loop(broadcaster, make_position())

    assert await drain(queue) == []


@pytest.mark.anyio
async def test_unsubscribe_is_safe_to_call_twice(
    broadcaster: PositionBroadcaster,
) -> None:
    """The SSE handler unsubscribes in a finally block that can run twice."""
    broadcaster.bind_loop(asyncio.get_running_loop())
    queue = broadcaster.subscribe()

    broadcaster.unsubscribe(queue)
    broadcaster.unsubscribe(queue)


def test_publishing_with_no_loop_bound_is_a_no_op(
    broadcaster: PositionBroadcaster,
) -> None:
    """Positions can arrive before the server's lifespan has run."""
    broadcaster.publish(make_position())


@pytest.mark.anyio
async def test_a_stalled_subscriber_drops_its_oldest_positions(
    broadcaster: PositionBroadcaster,
) -> None:
    """A browser tab that stops reading must not stall the radio thread or
    grow without limit; the newest fixes are the ones worth keeping."""
    broadcaster.bind_loop(asyncio.get_running_loop())
    queue = broadcaster.subscribe()
    overflow = queue.maxsize + 10

    publish_off_loop(
        broadcaster,
        *(make_position(latitude=float(i)) for i in range(overflow)),
    )

    items = await drain(queue)

    assert len(items) == queue.maxsize
    # The oldest were evicted, so the window ends on the most recent fix.
    assert items[-1]["latitude"] == float(overflow - 1)
    assert items[0]["latitude"] == float(overflow - queue.maxsize)


@pytest.mark.anyio
async def test_positions_arrive_in_order(broadcaster: PositionBroadcaster) -> None:
    broadcaster.bind_loop(asyncio.get_running_loop())
    queue = broadcaster.subscribe()

    publish_off_loop(broadcaster, *(make_position(latitude=float(i)) for i in range(5)))

    assert [item["latitude"] for item in await drain(queue)] == [
        0.0,
        1.0,
        2.0,
        3.0,
        4.0,
    ]
