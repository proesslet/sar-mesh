import { useCallback, useState } from "react";
import { toMessage } from "../lib/errors";

export interface AsyncAction {
  /** True while an action is in flight; controls are disabled against it. */
  busy: boolean;
  error: string | null;
  /** Report a failure from outside `run` -- a load that is not a mutation. */
  fail: (cause: unknown) => void;
  clearError: () => void;
  /**
   * Run `action`, showing it as busy and capturing any failure as `error`.
   * `onSuccess` fires only when the action resolved, and receives its result.
   */
  run: <T>(
    action: () => Promise<T>,
    onSuccess?: (result: T) => void,
  ) => Promise<void>;
}

/**
 * The busy/error bookkeeping every mutating control in the app needs.
 *
 * Each dialog used to hand-roll this: a `busy` flag, an `error` string and a
 * try/catch/finally that had to remember to clear both. Centralised so a new
 * dialog gets the same behaviour without re-deriving it -- and so a failure can
 * never leave the UI stuck busy.
 */
export function useAsyncAction(): AsyncAction {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = useCallback((cause: unknown) => setError(toMessage(cause)), []);
  const clearError = useCallback(() => setError(null), []);

  const run = useCallback(
    async <T>(action: () => Promise<T>, onSuccess?: (result: T) => void) => {
      setBusy(true);
      setError(null);

      try {
        const result = await action();
        onSuccess?.(result);
      } catch (cause) {
        setError(toMessage(cause));
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  return { busy, error, fail, clearError, run };
}
