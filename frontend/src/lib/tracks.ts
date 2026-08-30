import type { Position, TrackPoint } from "../api";

// A trail is cut where the silence is long enough that a straight line between
// two fixes would be a claim rather than an observation.
//
// Scaled off the node's own cadence, because a beacon interval is configured
// per radio and a gap only means anything relative to it. Clamped at both ends:
// below the floor the uncertainty is seconds of walking and a straight line is
// honest; above the ceiling no cadence justifies joining the ends up.
const GAP_FACTOR = 4;
const MIN_GAP_MS = 2 * 60 * 1000;
const MAX_GAP_MS = 10 * 60 * 1000;

/** An unbroken stretch of a trail: fixes with no significant silence between. */
export interface TrackRun {
  points: TrackPoint[];
  // The final stretch of a tracker that has gone quiet -- where they were when
  // we lost them, as opposed to ground we watched them cover.
  dashed: boolean;
}

const at = (point: { received_at: string }) => Date.parse(point.received_at);

/**
 * Extend a fetched history with the fixes that have arrived since.
 *
 * Cut at the history's last timestamp rather than deduplicating point by
 * point: rxTime is whole seconds, so two beacons can share one, and nothing in
 * the trail payload tells them apart. Dropping a live fix that ties with the
 * last fetched one costs at most one point, which is invisible; keeping a
 * duplicate would draw a spur back to a position already left.
 */
export function mergeTrack(
  history: TrackPoint[],
  tail: Position[],
): TrackPoint[] {
  const last = history.length ? at(history[history.length - 1]) : -Infinity;

  const arrived = tail
    .filter((position) => at(position) > last)
    .sort((a, b) => at(a) - at(b))
    .map(({ latitude, longitude, received_at }) => ({
      latitude,
      longitude,
      received_at,
    }));

  return arrived.length ? [...history, ...arrived] : history;
}

/**
 * How long a silence has to be, for this node, before it breaks the trail.
 *
 * Median rather than mean: the mean is dragged upwards by exactly the gaps
 * being looked for, which would stop them registering.
 */
function gapThreshold(points: TrackPoint[]): number {
  const gaps: number[] = [];

  for (let index = 1; index < points.length; index += 1) {
    gaps.push(at(points[index]) - at(points[index - 1]));
  }

  if (gaps.length === 0) return MAX_GAP_MS;

  gaps.sort((a, b) => a - b);
  const median = gaps[Math.floor(gaps.length / 2)];

  return Math.min(MAX_GAP_MS, Math.max(MIN_GAP_MS, GAP_FACTOR * median));
}

/**
 * Split a trail where the mesh stopped hearing the tracker.
 *
 * Drawn as separate lines rather than one line with a dashed connector: a
 * break says "not observed", which is exactly true, where a connector would
 * still put a line through ground nobody was seen to cross.
 *
 * Runs of a single fix are dropped -- there is no line to draw through one
 * point, and the marker already shows where it was.
 */
export function toTrackRuns(points: TrackPoint[], stale: boolean): TrackRun[] {
  if (points.length < 2) return [];

  const threshold = gapThreshold(points);
  const runs: TrackPoint[][] = [[points[0]]];

  for (let index = 1; index < points.length; index += 1) {
    const silence = at(points[index]) - at(points[index - 1]);

    if (silence > threshold) runs.push([]);

    runs[runs.length - 1].push(points[index]);
  }

  const drawable = runs.filter((run) => run.length >= 2);

  return drawable.map((run, index) => ({
    points: run,
    // Only the last stretch: dashing the whole trail would cast doubt on
    // ground that was genuinely watched.
    dashed: stale && index === drawable.length - 1,
  }));
}
