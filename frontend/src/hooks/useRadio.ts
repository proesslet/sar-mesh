import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api";
import type { RadioInfo } from "../api";
import { toMessage } from "../lib/errors";

export interface RadioState {
  radio: RadioInfo | null;
  /** True while no node is attached, which is a normal state, not a failure. */
  disconnected: boolean;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/**
 * The attached node's identity, refetchable.
 *
 * Unlike the other settings panels this one has a reload: an operator who
 * opens settings because the map went quiet may well plug the radio in while
 * the dialog is still up, and closing and reopening it to find out whether
 * that worked is the wrong thing to make them do.
 */
export function useRadio(): RadioState {
  const [radio, setRadio] = useState<RadioInfo | null>(null);
  const [disconnected, setDisconnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => {
    setLoading(true);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    api
      .radio()
      .then((next) => {
        if (cancelled) return;

        setRadio(next);
        setDisconnected(false);
        setError(null);
      })
      .catch((cause) => {
        if (cancelled) return;

        setRadio(null);

        const unplugged = cause instanceof ApiError && cause.status === 503;

        setDisconnected(unplugged);
        setError(unplugged ? null : toMessage(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return { radio, disconnected, error, loading, reload };
}
