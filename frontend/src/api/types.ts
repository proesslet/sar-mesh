export interface TrackerAssignment {
  incident_id: string;
  incident_name: string | null;
  team_id: string;
  team_name: string | null;
}

export interface Tracker {
  node_id: string;
  label: string;
  assignment: TrackerAssignment | null;
}

export interface UnregisteredNode {
  node_id: string;
  node_num: number;
  last_seen_at: string;
}

export interface Team {
  id: string;
  name: string;
  personnel_count: number;
  tracker_count: number;
}

export interface Incident {
  id: string;
  name: string;
  started_at: string;
  ended_at: string | null;
}

export interface Position {
  node_id: string;
  node_num: number;
  latitude: number;
  longitude: number;
  received_at: string;
  satellites: number | null;
  precision_bits: number | null;
  rssi: number | null;
  snr: number | null;
}

export interface TrackerStatus {
  tracker: Tracker;
  team: Team | null;
  position: Position | null;
  last_seen_at: string | null;
}

/** One fix on a trail: only what the polyline needs. */
export interface TrackPoint {
  latitude: number;
  longitude: number;
  received_at: string;
}

export interface Track {
  node_id: string;
  // Older fixes were dropped to fit the limit, so the trail starts later than
  // the window asked for.
  truncated: boolean;
  points: TrackPoint[];
}

/**
 * A node heard on the mesh, whether or not it is working this incident.
 *
 * Named MeshNode because `Node` is a DOM global, and shadowing it in a file
 * that also touches Leaflet produces errors that read as nonsense.
 */
export interface MeshNode {
  node_id: string;
  node_num: number;
  // null for a node that has never been registered as a tracker.
  label: string | null;
  team: Team | null;
  position: Position;
}

export interface Basemap {
  available: boolean;
  name?: string | null;
  minzoom?: number | null;
  maxzoom?: number | null;
  bounds?: string | null;
  revision: number;
}

export interface BasemapPack {
  name: string;
  path: string;
  size_bytes: number;
  active: boolean;
  readable: boolean;
  title: string | null;
  minzoom: number | null;
  maxzoom: number | null;
  bounds: string | null;
}

export interface OnlineSource {
  url_template: string;
  enabled: boolean;

  bulk_allowed: boolean;
  attribution: string | null;
}

export interface BasemapLibrary {
  directory: string | null;
  active: string | null;
  revision: number;
  packs: BasemapPack[];
  online: OnlineSource;
}

/**
 * A geographic bounding box.
 *
 * Drawn on the map, then handed to the tile downloader
 **/
export interface Area {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface DownloadEstimate {
  tiles: number;
  limit: number;
  within_limit: boolean;
  suggested_max_zoom: number | null;
}

export interface DownloadProgress {
  name: string;
  state: "running" | "done" | "cancelled" | "failed";
  total: number;
  completed: number;
  failed: number;
  error: string | null;
  last_error: string | null;
}

export interface FileLocation {
  path: string;
  exists: boolean;
  size_bytes: number | null;
}

export interface Diagnostics {
  frozen: boolean;
  version: string;
  data_dir: string;
  database: FileLocation;
  log: FileLocation;
  basemap_dir: FileLocation | null;
}

export interface LogTail {
  path: string;
  exists: boolean;
  lines: string[];
}
