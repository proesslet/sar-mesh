export interface TrackerAssignment {
  incident_id: string;
  incident_name: string | null;
  team_id: string;
  team_name: string | null;
}

export interface Tracker {
  node_id: string;
  label: string;
  // Non-null while a team is carrying it, which is what blocks deletion.
  assignment: TrackerAssignment | null;
}

/** A node heard on the mesh that has no tracker record yet. */
export interface UnregisteredNode {
  node_id: string;
  node_num: number;
  last_seen_at: string;
}

export interface Team {
  id: string;
  name: string;
  personnel_count: number;
  // Trackers currently assigned to this team, which is what blocks deletion.
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

export interface Basemap {
  available: boolean;
  name?: string | null;
  minzoom?: number | null;
  maxzoom?: number | null;
  bounds?: string | null;
  // Changes whenever the active pack changes. Tile URLs are identical between
  // packs, so this is what lets the map bypass the browser's tile cache.
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
  // False for a source that may be viewed but not bulk-downloaded, so the
  // download form does not offer a URL the server will reject.
  bulk_allowed: boolean;
  // Set only while the default source is in use; a custom server's attribution
  // is not ours to guess.
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
 * Drawn on the map, then handed to the tile downloader. Declared once here so
 * the map and the download form cannot drift apart on field order or naming.
 */
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
  // The deepest zoom that would fit, when the request is over the limit.
  // null when it already fits, or when even the minimum zoom is too much.
  suggested_max_zoom: number | null;
}

export interface DownloadProgress {
  name: string;
  state: "running" | "done" | "cancelled" | "failed";
  total: number;
  completed: number;
  failed: number;
  error: string | null;
  // Why the last tile failed, while it is still running. A source that rejects
  // every request otherwise looks exactly like a stalled download.
  last_error: string | null;
}

export interface FileLocation {
  path: string;
  exists: boolean;
  size_bytes: number | null;
}

export interface Diagnostics {
  frozen: boolean;
  // "unknown" in a build with no distribution metadata to read.
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
