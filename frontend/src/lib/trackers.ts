import type { MeshNode, Position, TrackerStatus } from "../api";

const STALE_AFTER_MS = 10 * 60 * 1000;

export interface TrackerView {
  nodeId: string;
  label: string;
  team: string | null;
  // Carried alongside the name because colour has to key on something stable:
  // two teams can be renamed, but their ids do not move.
  teamId: string | null;
  position: Position;
  stale: boolean;
}

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
      teamId: status.team?.id ?? null,
      position,
      stale: now - new Date(position.received_at).getTime() > STALE_AFTER_MS,
    });
  }

  return views;
}

/**
 * Views for nodes heard on the mesh that the incident roster does not cover.
 *
 * Returned separately from the roster rather than merged into it: the roster
 * is what the sidebar counts and what the map frames itself on, and neither
 * should move because a stranger beaconed.
 *
 * A node arriving over SSE that is in neither list still gets a view, which is
 * what lets one appear without waiting for a refetch.
 */
export function toHeardViews(
  nodes: MeshNode[],
  statuses: TrackerStatus[],
  live: Record<string, Position>,
  now: number,
): TrackerView[] {
  const roster = new Set(statuses.map((status) => status.tracker.node_id));
  const labels = new Map<string, string | null>();
  const teams = new Map<string, { id: string; name: string } | null>();

  for (const node of nodes) {
    labels.set(node.node_id, node.label);
    teams.set(node.node_id, node.team);
  }

  const heard = new Set([...labels.keys(), ...Object.keys(live)]);
  const views: TrackerView[] = [];

  for (const nodeId of heard) {
    if (roster.has(nodeId)) continue;

    const position =
      live[nodeId] ?? nodes.find((node) => node.node_id === nodeId)?.position;

    if (!position) continue;

    const team = teams.get(nodeId) ?? null;

    views.push({
      nodeId,
      label: labels.get(nodeId) ?? nodeId,
      team: team?.name ?? null,
      teamId: team?.id ?? null,
      position,
      stale: now - new Date(position.received_at).getTime() > STALE_AFTER_MS,
    });
  }

  return views;
}
