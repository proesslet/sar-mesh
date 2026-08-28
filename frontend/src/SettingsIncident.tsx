import { useState } from "react";
import { api } from "./api";
import type { Incident } from "./api";

export function SettingsIncident({
  incident,
  onChange,
}: {
  incident: Incident | null;
  // Fired after a rename or an end, so the header reflects the change.
  onChange: () => void;
}) {
  const [name, setName] = useState(incident?.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [editing, setEditing] = useState(incident?.id ?? null);

  // The active incident can change while settings are open -- it is ended, or
  // a new one is started -- and the form has to follow. Keyed on the id rather
  // than the object so a refetch that returns the same incident does not wipe
  // whatever the operator was part-way through typing.
  if ((incident?.id ?? null) !== editing) {
    setEditing(incident?.id ?? null);
    setName(incident?.name ?? "");
    setConfirmEnd(false);
  }

  if (incident === null) {
    return (
      <section className="settings-section">
        <h3>Incident</h3>
        <p className="empty">
          No active incident. Start one to record positions against it.
        </p>
      </section>
    );
  }

  const trimmed = name.trim();
  const dirty = trimmed !== incident.name;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);

    try {
      await action();
      onChange();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settings-section">
      <h3>Incident</h3>

      {error && <p className="error">{error}</p>}

      <form
        className="settings-field"
        onSubmit={(event) => {
          event.preventDefault();
          if (dirty && trimmed) run(() => api.renameIncident(incident.id, trimmed));
        }}
      >
        <label htmlFor="incident-name">Name</label>
        <div className="settings-actions">
          <input
            id="incident-name"
            value={name}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" disabled={busy || !dirty || !trimmed}>
            Save
          </button>
        </div>
      </form>

      <p className="meta">
        Started {new Date(incident.started_at).toLocaleString()}
      </p>

      <div className="settings-actions">
        {confirmEnd ? (
          <>
            {/* Ending is what stops positions being recorded against this
                incident, and there is no undo, so it takes two clicks. */}
            <span className="meta">End {incident.name}?</span>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={() => run(() => api.endIncident(incident.id))}
            >
              End incident
            </button>
            <button type="button" onClick={() => setConfirmEnd(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirmEnd(true)}
          >
            End incident
          </button>
        )}
      </div>
    </section>
  );
}
