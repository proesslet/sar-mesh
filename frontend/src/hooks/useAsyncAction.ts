import { useCallback, useState } from "react";
import { toMessage } from "../lib/errors";

export interface AsyncAction {
  busy: boolean;
  error: string | null;
  fail: (cause: unknown) => void;
  clearError: () => void;
  run: <T>(
    action: () => Promise<T>,
    onSuccess?: (result: T) => void,
  ) => Promise<void>;
}

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
