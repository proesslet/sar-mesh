import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Area, DownloadProgress } from "./api";

// Remembered between sessions: a team fetches from the same source every time,
// and retyping a tile URL in the field is exactly the wrong moment for it.
const TEMPLATE_KEY = "sarmesh.tileUrlTemplate";

const POLL_MS = 1000;

function coordinates(area: Area): string {
  const round = (value: number) => value.toFixed(3);
  return `${round(area.west)}, ${round(area.south)} → ${round(area.east)}, ${round(area.north)}`;
}

export function SettingsDownload({
  area,
  suggestedUrl,
  onSelectArea,
  onFinished,
}: {
  area: Area | null;
  // The online map's URL, offered as the starting point: the tiles being
  // previewed are usually the tiles worth downloading.
  suggestedUrl: string;
  // Hands control back to the map so the operator can drag out a box.
  onSelectArea: () => void;
  onFinished: () => void;
}) {
  const [name, setName] = useState("");
  const [template, setTemplate] = useState(
    () => localStorage.getItem(TEMPLATE_KEY) ?? "",
  );

  // The suggestion comes from the library, which loads a render after this
  // form first appears, so it cannot simply seed the initial state. Adopted
  // only while the field is still empty -- a URL the operator typed, or used
  // last time, outranks it.
  const [offered, setOffered] = useState(suggestedUrl);

  if (suggestedUrl !== offered) {
    setOffered(suggestedUrl);
    if (template === "") setTemplate(suggestedUrl);
  }
  const [minZoom, setMinZoom] = useState(10);
  const [maxZoom, setMaxZoom] = useState(15);
  const [tiles, setTiles] = useState<number | null>(null);
  const [overLimit, setOverLimit] = useState(false);
  const [suggestedZoom, setSuggestedZoom] = useState<number | null>(null);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(() => {
    api
      .downloadStatus()
      .then((status) => {
        setProgress(status);

        // A finished download adds a pack to the library, so the list above
        // this form has to be refreshed.
        if (status?.state === "done") onFinished();
      })
      .catch(() => undefined);
  }, [onFinished]);

  // Picks up a download that was already running before settings were opened.
  useEffect(() => check(), [check]);

  // Polls only while something is actually downloading, and stops on its own
  // when the state moves off "running".
  useEffect(() => {
    if (progress?.state !== "running") return;

    const timer = window.setInterval(check, POLL_MS);
    return () => window.clearInterval(timer);
  }, [progress?.state, check]);

  // The tile count drives whether the request is even allowed, so it is
  // recomputed whenever the area or zoom range moves.
  useEffect(() => {
    if (!area) return;

    let cancelled = false;

    api
      .estimateDownload(area, minZoom, maxZoom)
      .then((estimate) => {
        if (cancelled) return;
        setTiles(estimate.tiles);
        setOverLimit(!estimate.within_limit);
        setSuggestedZoom(estimate.suggested_max_zoom);
      })
      .catch(() => {
        if (!cancelled) setTiles(null);
      });

    return () => {
      cancelled = true;
    };
  }, [area, minZoom, maxZoom]);

  const running = progress?.state === "running";

  async function start() {
    if (!area) return;

    setError(null);
    localStorage.setItem(TEMPLATE_KEY, template);

    try {
      // The response is already "running", so the polling effect picks it up.
      setProgress(
        await api.startDownload(name.trim(), template.trim(), area, minZoom, maxZoom),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  const ready =
    area != null && name.trim() !== "" && template.trim() !== "" && !overLimit;

  return (
    <div className="download">
      <h4>Download an area</h4>

      {error && <p className="error">{error}</p>}

      <div className="settings-field">
        <label htmlFor="tile-url">Tile URL</label>
        <input
          id="tile-url"
          placeholder="https://tiles.example.org/{z}/{x}/{y}.png"
          value={template}
          disabled={running}
          onChange={(event) => setTemplate(event.target.value)}
        />
        <p className="note">
          Your own tile server, or a provider whose terms allow bulk download.
          The OpenStreetMap public tile servers do not.
        </p>
      </div>

      <div className="settings-field">
        <label htmlFor="pack-name">Pack name</label>
        <input
          id="pack-name"
          placeholder="ridge-search"
          value={name}
          disabled={running}
          onChange={(event) => setName(event.target.value)}
        />
      </div>

      <div className="settings-field">
        <label>Area</label>
        <div className="settings-actions">
          <span className="meta">
            {area ? coordinates(area) : "No area selected"}
          </span>
          <button type="button" disabled={running} onClick={onSelectArea}>
            {area ? "Redraw on map" : "Select on map"}
          </button>
        </div>
      </div>

      <div className="settings-field">
        <label>Zoom range</label>
        <div className="settings-actions">
          <input
            type="number"
            min={0}
            max={22}
            value={minZoom}
            disabled={running}
            onChange={(event) => setMinZoom(Number(event.target.value))}
          />
          <span className="meta">to</span>
          <input
            type="number"
            min={0}
            max={22}
            value={maxZoom}
            disabled={running}
            onChange={(event) => setMaxZoom(Number(event.target.value))}
          />
        </div>
      </div>

      {tiles != null && (
        <p className={overLimit ? "error" : "meta"}>
          {tiles.toLocaleString()} tiles
          {overLimit &&
            (suggestedZoom != null ? (
              <>
                {" — too many. "}
                <button
                  type="button"
                  className="link"
                  onClick={() => setMaxZoom(suggestedZoom)}
                >
                  Use zoom {suggestedZoom}
                </button>
                {", or draw a smaller area."}
              </>
            ) : (
              " — too many, even at the minimum zoom. Draw a smaller area."
            ))}
        </p>
      )}

      <div className="settings-actions">
        {running ? (
          <>
            {/* Attempted, not fetched: a source that rejects everything would
                otherwise hold the bar at zero and read as a hang. */}
            <progress
              value={progress.completed + progress.failed}
              max={progress.total}
            />
            <span className="meta">
              {(progress.completed + progress.failed).toLocaleString()} /{" "}
              {progress.total.toLocaleString()}
            </span>
            <button type="button" onClick={() => api.cancelDownload()}>
              Cancel
            </button>
          </>
        ) : (
          <button type="button" disabled={!ready} onClick={start}>
            Download
          </button>
        )}
      </div>

      {/* Shown live rather than saved for the post-mortem: if every tile is
          being refused, that is worth knowing at tile 20, not at tile 5,000. */}
      {running && progress.failed > 0 && (
        <p className="error">
          {progress.failed.toLocaleString()} failed
          {progress.last_error && ` — ${progress.last_error}`}
        </p>
      )}

      {progress && !running && progress.state !== "done" && (
        <p className={progress.state === "failed" ? "error" : "meta"}>
          {progress.state === "failed"
            ? (progress.error ?? "The download failed")
            : `Cancelled after ${progress.completed.toLocaleString()} tiles`}
        </p>
      )}

      {progress?.state === "done" && (
        <p className="meta">
          {progress.name} saved
          {/* Missing tiles are normal at the edges of a provider's coverage,
              so this is reported rather than treated as a failure. */}
          {progress.failed > 0 &&
            ` — ${progress.failed.toLocaleString()} tiles were unavailable`}
        </p>
      )}
    </div>
  );
}
