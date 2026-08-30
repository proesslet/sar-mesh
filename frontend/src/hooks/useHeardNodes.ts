import { useEffect, useState } from "react";
import { api } from "../api";
import type { MeshNode } from "../api";
import { toMessage } from "../lib/errors";
import type { ConnectionState } from "./useLivePositions";

/**
 * Every node heard on the mesh, for the wider map scope.
 *
 * Only the roster a node belongs to has to be fetched -- once one is on the
 * map, its later beacons arrive over SSE like anything else. Refetched when the
 * stream reconnects, since a node first heard during a dropout would otherwise
 * be missing until the operator reloaded.
 */
export function useHeardNodes(
  incidentId: string | null,
  enabled: boolean,
  connection: ConnectionState,
) {
  const [nodes, setNodes] = useState<MeshNode[]>([]);
  const [error, setError] = useState<string | null>(null);

  const live = connection === "live";

  useEffect(() => {
    if (!enabled || incidentId === null) return;

    let cancelled = false;

    api
      .nodes()
      .then((next) => {
        if (!cancelled) {
          setNodes(next);
          setError(null);
        }
      })
      .catch((cause) => {
        if (!cancelled) setError(toMessage(cause));
      });

    return () => {
      cancelled = true;
    };
  }, [incidentId, enabled, live]);

  return { nodes: enabled ? nodes : [], error };
}
