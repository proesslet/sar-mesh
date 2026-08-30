import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { Area, DownloadEstimate, DownloadProgress } from "../../api";
import {
  Actions,
  Button,
  ErrorMessage,
  Field,
  Message,
  Meta,
  TextInput,
} from "../../components/ui";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { formatArea } from "../../lib/format";
import styles from "./SettingsDownload.module.css";

// Remembered between sessions: a team fetches from the same source every time,
// and retyping a tile URL in the field is exactly the wrong moment for it.
const TEMPLATE_KEY = "sarmesh.tileUrlTemplate";

const POLL_MS = 1000;

const DEFAULT_MIN_ZOOM = 10;
const DEFAULT_MAX_ZOOM = 15;

/** How big the request is, and what to do about it when it is too big. */
function EstimateNote({
  estimate,
  onUseZoom,
}: {
  estimate: DownloadEstimate;
  onUseZoom: (zoom: number) => void;
}) {
  const tiles = estimate.tiles.toLocaleString();

  if (estimate.within_limit) return <Meta>{tiles} tiles</Meta>;

  return (
    <Message tone="error">
      {tiles} tiles
      {estimate.suggested_max_zoom != null ? (
        <>
          {" — too many. "}
          <Button
            variant="link"
            onClick={() => onUseZoom(estimate.suggested_max_zoom!)}
          >
            Use zoom {estimate.suggested_max_zoom}
          </Button>
          {", or draw a smaller area."}
        </>
      ) : (
        " — too many, even at the minimum zoom. Draw a smaller area."
      )}
    </Message>
  );
}

/** What a finished, cancelled or failed download left behind. */
function DownloadOutcome({ progress }: { progress: DownloadProgress }) {
  if (progress.state === "failed") {
    return (
      <Message tone="error">{progress.error ?? "The download failed"}</Message>
    );
  }

  if (progress.state === "cancelled") {
    return (
      <Meta>Cancelled after {progress.completed.toLocaleString()} tiles</Meta>
    );
  }

  return (
    <Meta>
      {progress.name} saved
      {/* Missing tiles are normal at the edges of a provider's coverage, so
          this is reported rather than treated as a failure. */}
      {progress.failed > 0 &&
        ` — ${progress.failed.toLocaleString()} tiles were unavailable`}
    </Meta>
  );
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

  const [minZoom, setMinZoom] = useState(DEFAULT_MIN_ZOOM);
  const [maxZoom, setMaxZoom] = useState(DEFAULT_MAX_ZOOM);
  const [estimate, setEstimate] = useState<DownloadEstimate | null>(null);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const { error, run } = useAsyncAction();

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
      .then((next) => {
        if (!cancelled) setEstimate(next);
      })
      .catch(() => {
        if (!cancelled) setEstimate(null);
      });

    return () => {
      cancelled = true;
    };
  }, [area, minZoom, maxZoom]);

  const running = progress?.state === "running";
  const ready =
    area != null &&
    name.trim() !== "" &&
    template.trim() !== "" &&
    estimate?.within_limit !== false;

  function start() {
    if (!area) return;

    localStorage.setItem(TEMPLATE_KEY, template);

    // The response is already "running", so the polling effect picks it up.
    run(
      () =>
        api.startDownload(name.trim(), template.trim(), area, minZoom, maxZoom),
      setProgress,
    );
  }

  return (
    <div className={styles.download}>
      <h4>Download an area</h4>

      <ErrorMessage error={error} />

      <Field label="Tile URL" htmlFor="tile-url">
        <TextInput
          id="tile-url"
          placeholder="https://tiles.example.org/{z}/{x}/{y}.png"
          value={template}
          disabled={running}
          full
          onChange={(event) => setTemplate(event.target.value)}
        />
        <Message>
          Your own tile server, or a provider whose terms allow bulk download.
          The OpenStreetMap public tile servers do not.
        </Message>
      </Field>

      <Field label="Pack name" htmlFor="pack-name">
        <TextInput
          id="pack-name"
          placeholder="ridge-search"
          value={name}
          disabled={running}
          full
          onChange={(event) => setName(event.target.value)}
        />
      </Field>

      <Field label="Area">
        <Actions>
          <Meta>{area ? formatArea(area) : "No area selected"}</Meta>
          <Button disabled={running} onClick={onSelectArea}>
            {area ? "Redraw on map" : "Select on map"}
          </Button>
        </Actions>
      </Field>

      <Field label="Zoom range">
        <Actions>
          <TextInput
            type="number"
            aria-label="Minimum zoom"
            min={0}
            max={22}
            value={minZoom}
            disabled={running}
            onChange={(event) => setMinZoom(Number(event.target.value))}
          />
          <Meta>to</Meta>
          <TextInput
            type="number"
            aria-label="Maximum zoom"
            min={0}
            max={22}
            value={maxZoom}
            disabled={running}
            onChange={(event) => setMaxZoom(Number(event.target.value))}
          />
        </Actions>
      </Field>

      {estimate && <EstimateNote estimate={estimate} onUseZoom={setMaxZoom} />}

      <Actions>
        {running ? (
          <>
            {/* Attempted, not fetched: a source that rejects everything would
                otherwise hold the bar at zero and read as a hang. */}
            <progress
              value={progress.completed + progress.failed}
              max={progress.total}
            />
            <Meta>
              {(progress.completed + progress.failed).toLocaleString()} /{" "}
              {progress.total.toLocaleString()}
            </Meta>
            <Button
              onClick={() => run(() => api.cancelDownload(), setProgress)}
            >
              Cancel
            </Button>
          </>
        ) : (
          <Button disabled={!ready} onClick={start}>
            Download
          </Button>
        )}
      </Actions>

      {/* Shown live rather than saved for the post-mortem: if every tile is
          being refused, that is worth knowing at tile 20, not at tile 5,000. */}
      {running && progress.failed > 0 && (
        <Message tone="error">
          {progress.failed.toLocaleString()} failed
          {progress.last_error && ` — ${progress.last_error}`}
        </Message>
      )}

      {progress && !running && <DownloadOutcome progress={progress} />}
    </div>
  );
}
