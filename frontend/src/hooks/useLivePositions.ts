import { useEffect, useState } from "react";
import type { Position } from "../api";

export type ConnectionState = "connecting" | "live" | "lost";

/**
 * Subscribes to the server's SSE stream and keeps the latest position per node.
 *
 * EventSource reconnects on its own, so the hook only has to track whether the
 * stream is currently up in order to show it in the UI -- an operator needs to
 * know the difference between "no movement" and "not receiving".
 */
export function useLivePositions() {
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  useEffect(() => {
    const source = new EventSource("/events");

    source.onopen = () => setConnection("live");
    source.onerror = () => setConnection("lost");

    source.addEventListener("position", (event) => {
      const position = JSON.parse((event as MessageEvent).data) as Position;
      setConnection("live");
      setPositions((current) => ({ ...current, [position.node_id]: position }));
    });

    return () => source.close();
  }, []);

  return { positions, connection };
}
