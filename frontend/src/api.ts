export interface TrackerAssignment {
  incident_id: string
  incident_name: string | null
  team_id: string
  team_name: string | null
}

export interface Tracker {
  node_id: string
  label: string
  // Non-null while a team is carrying it, which is what blocks deletion.
  assignment: TrackerAssignment | null
}

/** A node heard on the mesh that has no tracker record yet. */
export interface UnregisteredNode {
  node_id: string
  node_num: number
  last_seen_at: string
}

export interface Team {
  id: string
  name: string
  personnel_count: number
  // Trackers currently assigned to this team, which is what blocks deletion.
  tracker_count: number
}

export interface Incident {
  id: string
  name: string
  started_at: string
  ended_at: string | null
}

export interface Position {
  node_id: string
  node_num: number
  latitude: number
  longitude: number
  received_at: string
  satellites: number | null
  precision_bits: number | null
  rssi: number | null
  snr: number | null
}

export interface TrackerStatus {
  tracker: Tracker
  team: Team | null
  position: Position | null
  last_seen_at: string | null
}

export interface Basemap {
  available: boolean
  name?: string | null
  minzoom?: number | null
  maxzoom?: number | null
  bounds?: string | null
  // Changes whenever the active pack changes. Tile URLs are identical between
  // packs, so this is what lets the map bypass the browser's tile cache.
  revision: number
}

export interface BasemapPack {
  name: string
  path: string
  size_bytes: number
  active: boolean
  readable: boolean
  title: string | null
  minzoom: number | null
  maxzoom: number | null
  bounds: string | null
}

export interface OnlineSource {
  url_template: string
  enabled: boolean
  // False for a source that may be viewed but not bulk-downloaded, so the
  // download form does not offer a URL the server will reject.
  bulk_allowed: boolean
  // Set only while the default source is in use; a custom server's attribution
  // is not ours to guess.
  attribution: string | null
}

export interface BasemapLibrary {
  directory: string | null
  active: string | null
  revision: number
  packs: BasemapPack[]
  online: OnlineSource
}

export interface Area {
  west: number
  south: number
  east: number
  north: number
}

export interface DownloadEstimate {
  tiles: number
  limit: number
  within_limit: boolean
  // The deepest zoom that would fit, when the request is over the limit.
  // null when it already fits, or when even the minimum zoom is too much.
  suggested_max_zoom: number | null
}

export interface DownloadProgress {
  name: string
  state: 'running' | 'done' | 'cancelled' | 'failed'
  total: number
  completed: number
  failed: number
  error: string | null
  // Why the last tile failed, while it is still running. A source that rejects
  // every request otherwise looks exactly like a stalled download.
  last_error: string | null
}

export interface FileLocation {
  path: string
  exists: boolean
  size_bytes: number | null
}

export interface Diagnostics {
  frozen: boolean
  data_dir: string
  database: FileLocation
  log: FileLocation
  basemap_dir: FileLocation | null
}

export interface LogTail {
  path: string
  exists: boolean
  lines: string[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    throw new Error(await errorMessage(response))
  }

  return response.json() as Promise<T>
}

// FastAPI reports failures as {"detail": ...}. Unwrapped here so the operator
// reads the message rather than the JSON envelope around it.
async function errorMessage(response: Response): Promise<string> {
  const fallback = `${response.status} ${response.statusText}`
  const body = await response.text()

  if (!body) return fallback

  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (detail != null) return JSON.stringify(detail)
  } catch {
    // Not JSON -- a proxy error page, say. The raw body is still the best
    // description available.
  }

  return body
}

export const api = {
  status: () => request<TrackerStatus[]>('/api/status'),
  trackers: () => request<Tracker[]>('/api/trackers'),
  teams: () => request<Team[]>('/api/teams'),
  incidents: () => request<Incident[]>('/api/incidents'),
  activeIncident: () => request<Incident | null>('/api/incidents/active'),
  basemap: () => request<Basemap>('/api/basemap'),

  createIncident: (name: string) =>
    request<Incident>('/api/incidents', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  createTeam: (name: string, personnel_count: number) =>
    request<Team>('/api/teams', {
      method: 'POST',
      body: JSON.stringify({ name, personnel_count }),
    }),

  // Returns the remaining teams, so the list cannot drift from the server.
  deleteTeam: (id: string) =>
    request<Team[]>(`/api/teams/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),

  createTracker: (node_id: string, label: string) =>
    request<Tracker>('/api/trackers', {
      method: 'POST',
      body: JSON.stringify({ node_id, label }),
    }),

  unregisteredNodes: () =>
    request<UnregisteredNode[]>('/api/trackers/unregistered'),

  // Returns the remaining trackers, so the list cannot drift from the server.
  deleteTracker: (node_id: string) =>
    request<Tracker[]>(`/api/trackers/${encodeURIComponent(node_id)}`, {
      method: 'DELETE',
    }),

  assign: (incident_id: string, tracker_node_id: string, team_id: string) =>
    request<unknown>('/api/assignments', {
      method: 'POST',
      body: JSON.stringify({ incident_id, tracker_node_id, team_id }),
    }),

  // Returns the trackers, whose assignment state is what the caller shows.
  unassign: (tracker_node_id: string) =>
    request<Tracker[]>(
      `/api/assignments/${encodeURIComponent(tracker_node_id)}`,
      { method: 'DELETE' },
    ),

  renameIncident: (id: string, name: string) =>
    request<Incident>(`/api/incidents/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),

  endIncident: (id: string) =>
    request<Incident>(`/api/incidents/${encodeURIComponent(id)}/end`, {
      method: 'POST',
    }),

  basemaps: () => request<BasemapLibrary>('/api/basemaps'),

  // null turns the basemap off; positions still plot without one.
  selectBasemap: (name: string | null) =>
    request<BasemapLibrary>('/api/basemaps/select', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  setOnlineSource: (url_template: string, enabled: boolean) =>
    request<BasemapLibrary>('/api/basemaps/online', {
      method: 'POST',
      body: JSON.stringify({ url_template, enabled }),
    }),

  estimateDownload: (area: Area, min_zoom: number, max_zoom: number) =>
    request<DownloadEstimate>('/api/basemaps/estimate', {
      method: 'POST',
      body: JSON.stringify({ ...area, min_zoom, max_zoom }),
    }),

  startDownload: (
    name: string,
    url_template: string,
    area: Area,
    min_zoom: number,
    max_zoom: number,
  ) =>
    request<DownloadProgress>('/api/basemaps/download', {
      method: 'POST',
      body: JSON.stringify({ name, url_template, ...area, min_zoom, max_zoom }),
    }),

  downloadStatus: () => request<DownloadProgress | null>('/api/basemaps/download'),

  cancelDownload: () =>
    request<DownloadProgress | null>('/api/basemaps/download/cancel', {
      method: 'POST',
    }),

  diagnostics: () => request<Diagnostics>('/api/diagnostics'),

  log: (lines = 200) => request<LogTail>(`/api/diagnostics/log?lines=${lines}`),
}

/**
 * Import an MBTiles pack by streaming its bytes to the server.
 *
 * XMLHttpRequest rather than fetch: packs run to gigabytes and fetch cannot
 * report upload progress, which would leave the operator watching a frozen
 * dialog for minutes with no way to tell import from hang.
 */
export function uploadBasemap(
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<BasemapLibrary> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/basemaps/${encodeURIComponent(file.name)}`)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as BasemapLibrary)
        return
      }
      reject(new Error(xhr.responseText || `${xhr.status} ${xhr.statusText}`))
    }

    xhr.onerror = () => reject(new Error('The upload failed'))
    xhr.onabort = () => reject(new Error('The upload was cancelled'))

    signal?.addEventListener('abort', () => xhr.abort(), { once: true })

    xhr.send(file)
  })
}
