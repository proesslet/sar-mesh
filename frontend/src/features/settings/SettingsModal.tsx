import { useRef, useState } from "react";
import type { ReactNode } from "react";
import type { Area, Incident } from "../../api";
import { Modal } from "../../components/Modal";
import { useDiagnostics } from "../../hooks/useDiagnostics";
import { SettingsAbout } from "./SettingsAbout";
import { SettingsBasemaps } from "./SettingsBasemaps";
import { SettingsDiagnostics } from "./SettingsDiagnostics";
import { SettingsIncident } from "./SettingsIncident";
import { SettingsRadio } from "./SettingsRadio";
import styles from "./SettingsModal.module.css";

const CATEGORIES = [
  { id: "radio", label: "Radio" },
  { id: "incident", label: "Incident" },
  { id: "map", label: "Map" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "about", label: "About" },
] as const;

type CategoryId = (typeof CATEGORIES)[number]["id"];

/**
 * The category rail.
 *
 * A real tablist rather than a column of buttons, so the arrow keys move
 * between categories -- this is a dialog an operator may well be driving from
 * the keyboard with one hand on a radio.
 */
function SettingsNav({
  current,
  onSelect,
}: {
  current: CategoryId;
  onSelect: (id: CategoryId) => void;
}) {
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  function move(event: React.KeyboardEvent) {
    const index = CATEGORIES.findIndex((category) => category.id === current);
    const last = CATEGORIES.length - 1;
    let next: number;

    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        next = index === last ? 0 : index + 1;
        break;
      case "ArrowUp":
      case "ArrowLeft":
        next = index === 0 ? last : index - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }

    event.preventDefault();
    onSelect(CATEGORIES[next].id);
    tabs.current[next]?.focus();
  }

  return (
    <div
      className={styles.nav}
      role="tablist"
      aria-label="Settings categories"
      aria-orientation="vertical"
      onKeyDown={move}
    >
      {CATEGORIES.map((category, index) => (
        <button
          key={category.id}
          ref={(element) => {
            tabs.current[index] = element;
          }}
          type="button"
          role="tab"
          id={`settings-tab-${category.id}`}
          aria-controls={`settings-panel-${category.id}`}
          aria-selected={category.id === current}
          // Roving tabindex: one stop for the whole rail, then the arrow keys
          // move within it.
          tabIndex={category.id === current ? 0 : -1}
          className={styles.tab}
          onClick={() => onSelect(category.id)}
        >
          {category.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Panels stay mounted and are hidden rather than unmounted.
 *
 * Switching category must not abandon work in progress: a map pack import can
 * run for minutes, and unmounting its panel would abort the upload.
 */
function Panel({
  id,
  current,
  children,
}: {
  id: CategoryId;
  current: CategoryId;
  children: ReactNode;
}) {
  return (
    <div
      className={styles.panel}
      role="tabpanel"
      id={`settings-panel-${id}`}
      aria-labelledby={`settings-tab-${id}`}
      hidden={id !== current}
    >
      {children}
    </div>
  );
}

interface SettingsProps {
  incident: Incident | null;
  area: Area | null;
  onClose: () => void;
  onBasemapChange: () => void;
  onIncidentChange: () => void;
  onSelectArea: () => void;
}

export function SettingsModal({
  open,
  ...props
}: SettingsProps & { open: boolean }) {
  // Not rendered while closed, so each section fetches on open rather than
  // holding data that went stale the moment the dialog was dismissed. That
  // also resets the dialog to its first category each time it opens.
  if (!open) return null;

  return <SettingsContent {...props} />;
}

/**
 * Split from the wrapper above so the early return stays free of hooks: the
 * dialog's state should not survive being closed and reopened.
 */
function SettingsContent({
  incident,
  area,
  onClose,
  onBasemapChange,
  onIncidentChange,
  onSelectArea,
}: SettingsProps) {
  const [current, setCurrent] = useState<CategoryId>("radio");
  const { diagnostics, error } = useDiagnostics();

  return (
    <Modal open title="Settings" onClose={onClose} size="lg" flush>
      <div className={styles.layout}>
        <SettingsNav current={current} onSelect={setCurrent} />

        <Panel id="radio" current={current}>
          <SettingsRadio />
        </Panel>

        <Panel id="incident" current={current}>
          <SettingsIncident incident={incident} onChange={onIncidentChange} />
        </Panel>

        <Panel id="map" current={current}>
          <SettingsBasemaps
            onChange={onBasemapChange}
            area={area}
            onSelectArea={onSelectArea}
          />
        </Panel>

        <Panel id="diagnostics" current={current}>
          <SettingsDiagnostics diagnostics={diagnostics} error={error} />
        </Panel>

        <Panel id="about" current={current}>
          <SettingsAbout version={diagnostics?.version ?? null} />
        </Panel>
      </div>
    </Modal>
  );
}
