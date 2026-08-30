import type {
  Area,
  Basemap,
  BasemapLibrary,
  Diagnostics,
  DownloadEstimate,
  DownloadProgress,
  Incident,
  LogTail,
  MeshNode,
  RadioInfo,
  Team,
  Track,
  Tracker,
  TrackerStatus,
  UnregisteredNode,
} from "./types";

/**
 * A failure the server described, carrying the status alongside the message.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

// FastAPI reports failures as {"detail": ...}. Unwrapped here so the operator
// reads the message rather than the JSON envelope around it.
async function errorMessage(response: Response): Promise<string> {
  const fallback = `${response.status} ${response.statusText}`;
  const body = await response.text();

  if (!body) return fallback;

  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail != null) return JSON.stringify(detail);
  } catch {
    // Not JSON -- a proxy error page, say. The raw body is still the best
    // description available.
  }

  return body;
}

const id = encodeURIComponent;

export const api = {
  status: () => request<TrackerStatus[]>("/api/status"),

  radio: () => request<RadioInfo>("/api/radio"),

  // Every node heard on the mesh, including ones no team is carrying.
  nodes: () => request<MeshNode[]>("/api/nodes"),

  tracks: (since?: Date) =>
    request<Track[]>(
      since ? `/api/tracks?since=${id(since.toISOString())}` : "/api/tracks",
    ),

  trackers: () => request<Tracker[]>("/api/trackers"),
  teams: () => request<Team[]>("/api/teams"),
  incidents: () => request<Incident[]>("/api/incidents"),
  activeIncident: () => request<Incident | null>("/api/incidents/active"),
  basemap: () => request<Basemap>("/api/basemap"),

  createIncident: (name: string) =>
    request<Incident>("/api/incidents", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  createTeam: (name: string, personnel_count: number) =>
    request<Team>("/api/teams", {
      method: "POST",
      body: JSON.stringify({ name, personnel_count }),
    }),

  deleteTeam: (teamId: string) =>
    request<Team[]>(`/api/teams/${id(teamId)}`, { method: "DELETE" }),

  createTracker: (node_id: string, label: string) =>
    request<Tracker>("/api/trackers", {
      method: "POST",
      body: JSON.stringify({ node_id, label }),
    }),

  unregisteredNodes: () =>
    request<UnregisteredNode[]>("/api/trackers/unregistered"),

  deleteTracker: (nodeId: string) =>
    request<Tracker[]>(`/api/trackers/${id(nodeId)}`, { method: "DELETE" }),

  assign: (incident_id: string, tracker_node_id: string, team_id: string) =>
    request<unknown>("/api/assignments", {
      method: "POST",
      body: JSON.stringify({ incident_id, tracker_node_id, team_id }),
    }),

  unassign: (nodeId: string) =>
    request<Tracker[]>(`/api/assignments/${id(nodeId)}`, { method: "DELETE" }),

  renameIncident: (incidentId: string, name: string) =>
    request<Incident>(`/api/incidents/${id(incidentId)}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  endIncident: (incidentId: string) =>
    request<Incident>(`/api/incidents/${id(incidentId)}/end`, {
      method: "POST",
    }),

  basemaps: () => request<BasemapLibrary>("/api/basemaps"),

  // null turns the basemap off; positions still plot without one.
  selectBasemap: (name: string | null) =>
    request<BasemapLibrary>("/api/basemaps/select", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  setOnlineSource: (url_template: string, enabled: boolean) =>
    request<BasemapLibrary>("/api/basemaps/online", {
      method: "POST",
      body: JSON.stringify({ url_template, enabled }),
    }),

  estimateDownload: (area: Area, min_zoom: number, max_zoom: number) =>
    request<DownloadEstimate>("/api/basemaps/estimate", {
      method: "POST",
      body: JSON.stringify({ ...area, min_zoom, max_zoom }),
    }),

  startDownload: (
    name: string,
    url_template: string,
    area: Area,
    min_zoom: number,
    max_zoom: number,
  ) =>
    request<DownloadProgress>("/api/basemaps/download", {
      method: "POST",
      body: JSON.stringify({ name, url_template, ...area, min_zoom, max_zoom }),
    }),

  downloadStatus: () =>
    request<DownloadProgress | null>("/api/basemaps/download"),

  cancelDownload: () =>
    request<DownloadProgress | null>("/api/basemaps/download/cancel", {
      method: "POST",
    }),

  diagnostics: () => request<Diagnostics>("/api/diagnostics"),

  log: (lines = 200) => request<LogTail>(`/api/diagnostics/log?lines=${lines}`),
};

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
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/basemaps/${id(file.name)}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as BasemapLibrary);
        return;
      }
      reject(new Error(xhr.responseText || `${xhr.status} ${xhr.statusText}`));
    };

    xhr.onerror = () => reject(new Error("The upload failed"));
    xhr.onabort = () => reject(new Error("The upload was cancelled"));

    signal?.addEventListener("abort", () => xhr.abort(), { once: true });

    xhr.send(file);
  });
}
