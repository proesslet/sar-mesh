import type { Position, TrackerStatus } from "../api";

// A tracker that has not beaconed in this long is shown as stale. Meshtastic
// nodes typically beacon every few minutes, so this is several missed cycles
// rather than a single dropped packet.
const STALE_AFTER_MS = 10 * 60 * 1000;

/**
 * One tracker as the operator sees it: a known position and whether it is
 * still current. Drawn identically by the map and the sidebar, so it is
 * derived once here rather than twice at each of them.
 */
export interface TrackerView {
  nodeId: string;
  label: string;
  team: string | null;
  position: Position;
  stale: boolean;
}

/**
 * Merge the roster from the server with positions arriving over SSE.
 *
 * Live positions win over the snapshot loaded at startup. A tracker with no
 * position at all is dropped: there is nowhere to draw it and nothing to say
 * about it beyond what the Trackers dialog already shows.
 */
export function toTrackerViews(
  statuses: TrackerStatus[],
  live: Record<string, Position>,
  now: number,
): TrackerView[] {
  const views: TrackerView[] = [];

  for (const status of statuses) {
    const position = live[status.tracker.node_id] ?? status.position;
    if (!position) continue;

    views.push({
      nodeId: status.tracker.node_id,
      label: status.tracker.label,
      team: status.team?.name ?? null,
      position,
      stale: now - new Date(position.received_at).getTime() > STALE_AFTER_MS,
    });
  }

  return views;
}
