import { useCallback, useEffect, useRef, useState } from "react";
import { api, uploadBasemap } from "../../api";
import type {
  Area,
  BasemapLibrary,
  BasemapPack,
  OnlineSource,
} from "../../api";
import {
  Actions,
  Button,
  ErrorMessage,
  Form,
  List,
  ListItem,
  Message,
  Section,
  TextInput,
} from "../../components/ui";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { cx } from "../../lib/cx";
import { formatSize } from "../../lib/format";
import { SettingsDownload } from "./SettingsDownload";
import styles from "./SettingsBasemaps.module.css";

/** The one-line summary under a pack's name: what it holds and how big it is. */
function packDetail(pack: BasemapPack): string {
  if (!pack.readable) return "Not a readable MBTiles pack";

  const zooms =
    pack.minzoom != null && pack.maxzoom != null
      ? `z${pack.minzoom}-${pack.maxzoom}`
      : null;

  return [pack.title, zooms, formatSize(pack.size_bytes)]
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
    <div className={styles.onlineSource}>
      <label className={styles.option}>
        <input
          type="checkbox"
          checked={source.enabled}
          disabled={disabled}
          onChange={(event) => save(url, event.target.checked)}
        />
        <span className={styles.optionText}>
          <span className={styles.optionName}>Show online map</span>
          <span className={styles.optionMeta}>
            Drawn under the offline packs, for finding an area to download.
            Falls away on its own when there is no network.
          </span>
        </span>
      </label>

      {source.enabled && (
        <Form
          onSubmit={() => {
            if (dirty && url.trim()) save(url, true);
          }}
        >
          <Actions>
            <TextInput
              aria-label="Online tile URL"
              value={url}
              disabled={disabled}
              onChange={(event) => setUrl(event.target.value)}
            />
            <Button type="submit" disabled={disabled || !dirty || !url.trim()}>
              Save
            </Button>
          </Actions>
        </Form>
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
  const [progress, setProgress] = useState<number | null>(null);
  const { busy, error, fail, run } = useAsyncAction();
  const fileInput = useRef<HTMLInputElement>(null);
  // Held so an in-flight import can be cancelled; a multi-gigabyte pack is not
  // something an operator should be stuck waiting on.
  const upload = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    api.basemaps().then(setLibrary).catch(fail);
  }, [fail]);

  useEffect(() => {
    refresh();
    return () => upload.current?.abort();
  }, [refresh]);

  function select(name: string | null) {
    run(
      () => api.selectBasemap(name),
      (next) => {
        setLibrary(next);
        onChange();
      },
    );
  }

  async function importPack(file: File) {
    const controller = new AbortController();
    upload.current = controller;
    setProgress(0);

    await run(
      () => uploadBasemap(file, setProgress, controller.signal),
      setLibrary,
    );

    upload.current = null;
    setProgress(null);
    // Cleared so re-picking the same file after a failure still fires change.
    if (fileInput.current) fileInput.current.value = "";
  }

  const packs = library?.packs ?? [];

  return (
    <Section title="Offline maps">
      <ErrorMessage error={error} />

      {library && (
        <OnlineSourceField
          source={library.online}
          disabled={busy}
          onSaved={(next) => {
            setLibrary(next);
            onChange();
          }}
          onError={fail}
        />
      )}

      {library && packs.length === 0 && (
        <Message tone="empty">
          No map packs imported yet. Add an <code>.mbtiles</code> file below, or
          drop one into {library.directory}.
        </Message>
      )}

      <List>
        {packs.map((pack) => (
          <ListItem key={pack.name}>
            <label
              className={cx(styles.option, !pack.readable && styles.unusable)}
            >
              <input
                type="radio"
                name="basemap"
                checked={pack.active}
                // A corrupt pack is listed so the operator can see it, but
                // selecting it would only produce an empty map.
                disabled={busy || !pack.readable}
                onChange={() => select(pack.name)}
              />
              <span className={styles.optionText}>
                <span className={styles.optionName}>{pack.name}</span>
                <span className={styles.optionMeta}>{packDetail(pack)}</span>
              </span>
            </label>
          </ListItem>
        ))}

        <ListItem>
          <label className={styles.option}>
            <input
              type="radio"
              name="basemap"
              checked={library?.active == null}
              disabled={busy}
              onChange={() => select(null)}
            />
            <span className={styles.optionText}>
              <span className={styles.optionName}>No basemap</span>
              <span className={styles.optionMeta}>
                Plot positions on a blank map
              </span>
            </span>
          </label>
        </ListItem>
      </List>

      <Actions>
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
        <Button disabled={busy} onClick={() => fileInput.current?.click()}>
          Import .mbtiles
        </Button>

        {progress != null && (
          <>
            <progress value={progress} max={1} />
            <span className={styles.optionMeta}>
              {Math.round(progress * 100)}%
            </span>
            <Button onClick={() => upload.current?.abort()}>Cancel</Button>
          </>
        )}
      </Actions>

      <Message>
        Packs are stored in {library?.directory ?? "the map directory"}. Tiles
        are served from disk, so the map keeps working with no network.
      </Message>

      <SettingsDownload
        area={area}
        suggestedUrl={
          library?.online.bulk_allowed ? library.online.url_template : ""
        }
        onSelectArea={onSelectArea}
        onFinished={refresh}
      />
    </Section>
  );
}
