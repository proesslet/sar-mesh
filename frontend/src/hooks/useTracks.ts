import { useEffect, useState } from "react";
import { api } from "../api";
import type { Track } from "../api";
import { toMessage } from "../lib/errors";
import type { ConnectionState } from "./useLivePositions";

/**
 * The trail history behind each tracker.
 *
 * Refetched when the stream comes back up, not only on mount: a dropout leaves
 * a hole in the live tail that no amount of client-side merging can fill, and
 * the database has the fixes that were missed.
 */
export function useTracks(
  incidentId: string | null,
  windowHours: number | null,
  enabled: boolean,
  connection: ConnectionState,
) {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [error, setError] = useState<string | null>(null);

  const live = connection === "live";

  useEffect(() => {
    if (!enabled || incidentId === null) return;

    let cancelled = false;

    // Read from the clock here rather than from a ticking value, or changing
    // the window would refetch the whole history every tick.
    const since =
      windowHours === null
        ? undefined
        : new Date(Date.now() - windowHours * 60 * 60 * 1000);

    api
      .tracks(since)
      .then((next) => {
        if (!cancelled) {
          setTracks(next);
          setError(null);
        }
      })
      .catch((cause) => {
        if (!cancelled) setError(toMessage(cause));
      });

    return () => {
      cancelled = true;
    };
  }, [incidentId, windowHours, enabled, live]);

  // Emptied here rather than by clearing state in the effect: what is drawn
  // while tracks are switched off is a render-time question, and the fetched
  // history is worth keeping for when they are switched back on.
  return { tracks: enabled ? tracks : [], error };
}
