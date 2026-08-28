import { useState } from "react";
import { Modal } from "./Modal";
import { api } from "./api";

export function NewIncidentModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Not rendered while closed, so the field starts empty each time rather than
  // holding the name of an incident that was already created.
  if (!open) return null;

  const trimmed = name.trim();

  async function create() {
    setBusy(true);
    setError(null);

    try {
      await api.createIncident(trimmed);
      setName("");
      onCreated();
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title="New incident" onClose={onClose}>
      {error && <p className="error">{error}</p>}

      <form
        className="settings-field"
        onSubmit={(event) => {
          event.preventDefault();
          if (trimmed) create();
        }}
      >
        <label htmlFor="new-incident-name">Name</label>
        <div className="settings-actions">
          <input
            id="new-incident-name"
            placeholder="Ridge Search"
            value={name}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" disabled={busy || !trimmed}>
            Start
          </button>
        </div>
      </form>

      <p className="note">
        Positions and tracker assignments are recorded against the active
        incident. End it under Settings when the search is over.
      </p>
    </Modal>
  );
}
