import { useEffect, useState } from "react";
import type { Position } from "../api";

export type ConnectionState = "connecting" | "live" | "lost";

// Fixes kept per node since the page loaded, so a trail can be extended
// without refetching it. Long enough at any real beacon rate that this is only
// ever a tail on a history that has already been fetched.
const MAX_TAIL_POINTS = 600;

interface Feed {
  latest: Record<string, Position>;
  tail: Record<string, Position[]>;
}

const EMPTY: Feed = { latest: {}, tail: {} };

/**
 * Subscribes to the server's SSE stream and keeps the latest position per node,
 * plus a short tail of the ones before it.
 *
 * EventSource reconnects on its own, so the hook only has to track whether the
 * stream is currently up in order to show it in the UI -- an operator needs to
 * know the difference between "no movement" and "not receiving".
 *
 * Both halves live in one state object so a beacon costs a single render.
 */
export function useLivePositions() {
  const [feed, setFeed] = useState<Feed>(EMPTY);
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  useEffect(() => {
    const source = new EventSource("/events");

    source.onopen = () => setConnection("live");
    source.onerror = () => setConnection("lost");

    source.addEventListener("position", (event) => {
      const position = JSON.parse((event as MessageEvent).data) as Position;
      setConnection("live");

      setFeed((current) => {
        const previous = current.tail[position.node_id] ?? [];
        const extended = [...previous, position];

        return {
          latest: { ...current.latest, [position.node_id]: position },
          tail: {
            ...current.tail,
            [position.node_id]: extended.slice(-MAX_TAIL_POINTS),
          },
        };
      });
    });

    return () => source.close();
  }, []);

  return { positions: feed.latest, tail: feed.tail, connection };
}
