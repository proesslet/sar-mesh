import { useEffect, useState } from "react";
import { api } from "../api";
import type { Diagnostics } from "../api";
import { toMessage } from "../lib/errors";

/**
 * Where SARMesh is keeping things, and which build is running.
 *
 * Fetched once for the whole settings dialog: the Files panel wants the paths
 * and the About panel wants the version, and they are the same request.
 */
export function useDiagnostics() {
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    api
      .diagnostics()
      .then((next) => {
        if (!cancelled) setDiagnostics(next);
      })
      .catch((cause) => {
        if (!cancelled) setError(toMessage(cause));
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { diagnostics, error };
}
