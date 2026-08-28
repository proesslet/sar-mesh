import { Modal } from "./Modal";
import { SettingsBasemaps } from "./SettingsBasemaps";
import { SettingsDiagnostics } from "./SettingsDiagnostics";
import { SettingsIncident } from "./SettingsIncident";
import type { Area, Incident } from "./api";

type SettingsModalProps = {
  open: boolean;
  incident: Incident | null;
  area: Area | null;
  onClose: () => void;
  onBasemapChange: () => void;
  onIncidentChange: () => void;
  onSelectArea: () => void;
};

export function SettingsModal({
  open,
  incident,
  area,
  onClose,
  onBasemapChange,
  onIncidentChange,
  onSelectArea,
}: SettingsModalProps) {
  // Not rendered while closed, so each section fetches on open rather than
  // holding data that went stale the moment the dialog was dismissed.
  if (!open) return null;

  return (
    <Modal open={open} title="Settings" onClose={onClose} className="settings">
      <SettingsIncident incident={incident} onChange={onIncidentChange} />
      <SettingsBasemaps
        onChange={onBasemapChange}
        area={area}
        onSelectArea={onSelectArea}
      />
      <SettingsDiagnostics />
    </Modal>
  );
}
