import { useEffect, useState } from "react";

/**
 * A timestamp that advances on an interval.
 *
 * Elapsed-time labels have to keep counting up even while the mesh is quiet,
 * or a stalled tracker reads as fresh indefinitely. Components take the clock
 * from here rather than calling `Date.now()` as they render, so what they show
 * depends on this interval rather than on when React chose to re-render.
 */
export function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);

  return now;
}
