import { useCallback, useEffect, useState } from "react";
import { Modal } from "./Modal";
import { api } from "./api";
import type { Team } from "./api";

export function TeamsModal({
  open,
  onClose,
  onChanged,
}: {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [name, setName] = useState("");
  const [personnel, setPersonnel] = useState(2);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.teams().then(setTeams).catch(report);
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  function report(cause: unknown) {
    setError(cause instanceof Error ? cause.message : String(cause));
  }

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);

    try {
      await action();
      load();
      onChanged();
    } catch (cause) {
      report(cause);
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  const trimmed = name.trim();

  return (
    <Modal open={open} title="Teams" onClose={onClose} className="settings">
      {error && <p className="error">{error}</p>}

      <section className="settings-section">
        <h3>
          Teams <span className="count">{teams.length}</span>
        </h3>

        {teams.length === 0 && (
          <p className="empty">
            No teams yet. Add one below, then assign trackers to it.
          </p>
        )}

        <ul className="trackers">
          {teams.map((team) => (
            <li key={team.id}>
              <div className="tracker-row">
                <span className="label">{team.name}</span>
                <button
                  type="button"
                  className="link danger"
                  // A team holding trackers cannot be deleted: their positions
                  // would stop being attributed to anyone mid-search.
                  disabled={busy || team.tracker_count > 0}
                  title={
                    team.tracker_count > 0
                      ? `Holding ${team.tracker_count} tracker(s)`
                      : "Delete this team"
                  }
                  onClick={() => run(() => api.deleteTeam(team.id))}
                >
                  Delete
                </button>
              </div>
              <div className="meta">
                {team.personnel_count} personnel
                {team.tracker_count > 0 &&
                  ` · ${team.tracker_count} tracker${
                    team.tracker_count === 1 ? "" : "s"
                  }`}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="settings-section">
        <h3>Add a team</h3>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmed) {
              run(async () => {
                await api.createTeam(trimmed, personnel);
                setName("");
                setPersonnel(2);
              });
            }
          }}
        >
          <div className="settings-field">
            <label htmlFor="team-name">Name</label>
            <input
              id="team-name"
              placeholder="Alpha"
              value={name}
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <div className="settings-field">
            <label htmlFor="team-personnel">Personnel</label>
            <div className="settings-actions">
              <input
                id="team-personnel"
                type="number"
                min={0}
                max={99}
                value={personnel}
                disabled={busy}
                onChange={(event) => setPersonnel(Number(event.target.value))}
              />
              <button type="submit" disabled={busy || !trimmed}>
                Add
              </button>
            </div>
          </div>
        </form>
      </section>
    </Modal>
  );
}
