import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Basemap, Incident, OnlineSource, TrackerStatus } from "../api";
import { toMessage } from "../lib/errors";

export interface Overview {
  statuses: TrackerStatus[];
  incident: Incident | null;
  basemap: Basemap | null;
  online: OnlineSource | null;
  error: string | null;
  /** Re-read the active incident and the tracker roster hanging off it. */
  refreshIncident: () => void;
  /** Re-read which basemap is serving, after settings changed it. */
  refreshBasemap: () => void;
}

/**
 * The server-owned state the whole screen is drawn from.
 *
 * Every field is refetched rather than patched from a mutation's response: the
 * server decides what is active, and a dialog that guessed would drift from it.
 */
export function useOverview(): Overview {
  const [statuses, setStatuses] = useState<TrackerStatus[]>([]);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [basemap, setBasemap] = useState<Basemap | null>(null);
  const [online, setOnline] = useState<OnlineSource | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshBasemap = useCallback(() => {
    Promise.all([api.basemap(), api.basemaps()])
      .then(([current, library]) => {
        setBasemap(current);
        setOnline(library.online);
      })
      .catch((cause) => setError(toMessage(cause)));
  }, []);

  const refreshIncident = useCallback(() => {
    Promise.all([api.activeIncident(), api.status()])
      .then(([active, roster]) => {
        setIncident(active);
        setStatuses(roster);
      })
      .catch((cause) => setError(toMessage(cause)));
  }, []);

  useEffect(() => {
    refreshIncident();
    refreshBasemap();
  }, [refreshIncident, refreshBasemap]);

  return {
    statuses,
    incident,
    basemap,
    online,
    error,
    refreshIncident,
    refreshBasemap,
  };
}
