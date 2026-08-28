import { useCallback, useEffect, useRef, useState } from "react";
import { SettingsDownload } from "./SettingsDownload";
import { api, uploadBasemap } from "./api";
import type {
  Area,
  BasemapLibrary,
  BasemapPack,
  OnlineSource,
} from "./api";

function size(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`;
  if (bytes >= 1e3) return `${Math.round(bytes / 1e3)} kB`;
  return `${bytes} B`;
}

function detail(pack: BasemapPack): string {
  if (!pack.readable) return "Not a readable MBTiles pack";

  const zooms =
    pack.minzoom != null && pack.maxzoom != null
      ? `z${pack.minzoom}-${pack.maxzoom}`
      : null;

  return [pack.title, zooms, size(pack.size_bytes)]
    .filter(Boolean)
    .join(" · ");
}

/**
 * The online map drawn behind the offline packs.
 *
 * Without it a fresh install shows a blank rectangle, which gives an operator
 * no way to tell where they are or to judge the area they are about to
 * download.
 */
function OnlineSourceField({
  source,
  disabled,
  onSaved,
  onError,
}: {
  source: OnlineSource;
  disabled: boolean;
  onSaved: (library: BasemapLibrary) => void;
  onError: (cause: unknown) => void;
}) {
  const [url, setUrl] = useState(source.url_template);
  const dirty = url.trim() !== source.url_template;

  function save(nextUrl: string, enabled: boolean) {
    api.setOnlineSource(nextUrl.trim(), enabled).then(onSaved).catch(onError);
  }

  return (
    <div className="online-source">
      <label className="checkbox">
        <input
          type="checkbox"
          checked={source.enabled}
          disabled={disabled}
          onChange={(event) => save(url, event.target.checked)}
        />
        <span>
          <span className="label">Show online map</span>
          <span className="meta">
            Drawn under the offline packs, for finding an area to download.
            Falls away on its own when there is no network.
          </span>
        </span>
      </label>

      {source.enabled && (
        <form
          className="settings-actions"
          onSubmit={(event) => {
            event.preventDefault();
            if (dirty && url.trim()) save(url, true);
          }}
        >
          <input
            aria-label="Online tile URL"
            value={url}
            disabled={disabled}
            onChange={(event) => setUrl(event.target.value)}
          />
          <button type="submit" disabled={disabled || !dirty || !url.trim()}>
            Save
          </button>
        </form>
      )}
    </div>
  );
}

export function SettingsBasemaps({
  onChange,
  area,
  onSelectArea,
}: {
  // Lets the map reload its tiles once a different pack is serving.
  onChange: () => void;
  area: Area | null;
  onSelectArea: () => void;
}) {
  const [library, setLibrary] = useState<BasemapLibrary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  // Held so an in-flight import can be cancelled; a multi-gigabyte pack is not
  // something an operator should be stuck waiting on.
  const upload = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    api.basemaps().then(setLibrary).catch(handleError);
  }, []);

  useEffect(() => {
    refresh();
    return () => upload.current?.abort();
  }, [refresh]);

  function handleError(cause: unknown) {
    setError(cause instanceof Error ? cause.message : String(cause));
  }

  async function select(name: string | null) {
    setBusy(true);
    setError(null);

    try {
      setLibrary(await api.selectBasemap(name));
      onChange();
    } catch (cause) {
      handleError(cause);
    } finally {
      setBusy(false);
    }
  }

  async function importPack(file: File) {
    const controller = new AbortController();
    upload.current = controller;
    setBusy(true);
    setError(null);
    setProgress(0);

    try {
      setLibrary(await uploadBasemap(file, setProgress, controller.signal));
    } catch (cause) {
      handleError(cause);
    } finally {
      upload.current = null;
      setBusy(false);
      setProgress(null);
      // Cleared so re-picking the same file after a failure still fires change.
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const packs = library?.packs ?? [];

  return (
    <section className="settings-section">
      <h3>Offline maps</h3>

      {error && <p className="error">{error}</p>}

      {library && (
        <OnlineSourceField
          source={library.online}
          disabled={busy}
          onSaved={(next) => {
            setLibrary(next);
            onChange();
          }}
          onError={handleError}
        />
      )}

      {library && packs.length === 0 && (
        <p className="empty">
          No map packs imported yet. Add an <code>.mbtiles</code> file below, or
          drop one into {library.directory}.
        </p>
      )}

      <ul className="options">
        {packs.map((pack) => (
          <li key={pack.name}>
            <label className={pack.readable ? "" : "unusable"}>
              <input
                type="radio"
                name="basemap"
                checked={pack.active}
                // A corrupt pack is listed so the operator can see it, but
                // selecting it would only produce an empty map.
                disabled={busy || !pack.readable}
                onChange={() => select(pack.name)}
              />
              <span>
                <span className="label">{pack.name}</span>
                <span className="meta">{detail(pack)}</span>
              </span>
            </label>
          </li>
        ))}

        <li>
          <label>
            <input
              type="radio"
              name="basemap"
              checked={library?.active == null}
              disabled={busy}
              onChange={() => select(null)}
            />
            <span>
              <span className="label">No basemap</span>
              <span className="meta">Plot positions on a blank map</span>
            </span>
          </label>
        </li>
      </ul>

      <div className="settings-actions">
        <input
          ref={fileInput}
          type="file"
          accept=".mbtiles"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) importPack(file);
          }}
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          Import .mbtiles
        </button>

        {progress != null && (
          <>
            <progress value={progress} max={1} />
            <span className="meta">{Math.round(progress * 100)}%</span>
            <button type="button" onClick={() => upload.current?.abort()}>
              Cancel
            </button>
          </>
        )}
      </div>

      <p className="note">
        Packs are stored in {library?.directory ?? "the map directory"}. Tiles
        are served from disk, so the map keeps working with no network.
      </p>

      <SettingsDownload
        area={area}
        suggestedUrl={
          library?.online.bulk_allowed ? library.online.url_template : ""
        }
        onSelectArea={onSelectArea}
        onFinished={refresh}
      />
    </section>
  );
}
