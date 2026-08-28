import { useCallback, useEffect, useState } from "react";
import { Modal } from "./Modal";
import { api } from "./api";
import type { Incident, Team, Tracker, UnregisteredNode } from "./api";

function age(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

/** Assign an unassigned tracker to a team, for the incident under way. */
function AssignControl({
  nodeId,
  teams,
  disabled,
  onAssign,
}: {
  nodeId: string;
  teams: Team[];
  disabled: boolean;
  onAssign: (nodeId: string, teamId: string) => void;
}) {
  const [teamId, setTeamId] = useState("");

  return (
    <div className="assign">
      <select
        aria-label={`Assign ${nodeId} to a team`}
        value={teamId}
        disabled={disabled}
        onChange={(event) => setTeamId(event.target.value)}
      >
        <option value="">Assign to…</option>
        {teams.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="link"
        disabled={disabled || !teamId}
        onClick={() => onAssign(nodeId, teamId)}
      >
        Assign
      </button>
    </div>
  );
}

export function TrackersModal({
  open,
  incident,
  onClose,
  onChanged,
}: {
  open: boolean;
  // Assignments belong to an incident, so there is nothing to assign to
  // until one is running.
  incident: Incident | null;
  onClose: () => void;
  // Trackers feed the map and the sidebar, so a change here has to reach them.
  onChanged: () => void;
}) {
  const [trackers, setTrackers] = useState<Tracker[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [heard, setHeard] = useState<UnregisteredNode[]>([]);
  const [nodeId, setNodeId] = useState("");
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.trackers(), api.unregisteredNodes(), api.teams()])
      .then(([list, nodes, teamList]) => {
        setTrackers(list);
        setHeard(nodes);
        setTeams(teamList);
      })
      .catch(report);
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

  function add(id: string, name: string) {
    run(async () => {
      await api.createTracker(id.trim(), name.trim());
      setNodeId("");
      setLabel("");
    });
  }

  if (!open) return null;

  const trimmedId = nodeId.trim();
  const trimmedLabel = label.trim();

  return (
    <Modal open={open} title="Trackers" onClose={onClose} className="settings">
      {error && <p className="error">{error}</p>}

      <section className="settings-section">
        <h3>
          Registered <span className="count">{trackers.length}</span>
        </h3>

        {trackers.length === 0 && (
          <p className="empty">
            No trackers yet. Add one below to start assigning it to a team.
          </p>
        )}

        <ul className="trackers">
          {trackers.map((tracker) => (
            <li key={tracker.node_id}>
              <div className="tracker-row">
                <span className="label">{tracker.label}</span>
                <button
                  type="button"
                  className="link danger"
                  // A tracker a team is carrying cannot be deleted: its
                  // positions would stop being attributed to anyone mid-search.
                  disabled={busy || tracker.assignment !== null}
                  title={
                    tracker.assignment
                      ? `Assigned to ${tracker.assignment.team_name ?? "a team"}`
                      : "Delete this tracker"
                  }
                  onClick={() => run(() => api.deleteTracker(tracker.node_id))}
                >
                  Delete
                </button>
              </div>
              <div className="meta">
                <code>{tracker.node_id}</code>
                {tracker.assignment
                  ? ` · ${tracker.assignment.team_name ?? "Assigned"}${
                      tracker.assignment.incident_name
                        ? ` · ${tracker.assignment.incident_name}`
                        : ""
                    }`
                  : " · Unassigned"}
              </div>

              {tracker.assignment ? (
                <div className="assign">
                  <button
                    type="button"
                    className="link"
                    disabled={busy}
                    onClick={() => run(() => api.unassign(tracker.node_id))}
                  >
                    Unassign
                  </button>
                </div>
              ) : (
                // Only offered with an incident to assign against and a team
                // to assign to; the reason is spelled out below the list
                // rather than left as a control that does nothing.
                incident !== null &&
                teams.length > 0 && (
                  <AssignControl
                    nodeId={tracker.node_id}
                    teams={teams}
                    disabled={busy}
                    onAssign={(nodeId, teamId) =>
                      run(() => api.assign(incident.id, nodeId, teamId))
                    }
                  />
                )
              )}
            </li>
          ))}
        </ul>

        {/* Both are preconditions for assigning, and neither is obvious from
            a row that simply has no control on it. */}
        {trackers.length > 0 && incident === null && (
          <p className="note">
            Start an incident to assign trackers to teams.
          </p>
        )}

        {trackers.length > 0 && incident !== null && teams.length === 0 && (
          <p className="note">Add a team before assigning trackers.</p>
        )}
      </section>

      <section className="settings-section">
        <h3>Add a tracker</h3>

        {heard.length > 0 && (
          <>
            <p className="note">
              Heard on the mesh but not registered. Pick one to fill in its ID.
            </p>
            <ul className="options">
              {heard.map((node) => (
                <li key={node.node_id}>
                  <div className="tracker-row">
                    <code>{node.node_id}</code>
                    <button
                      type="button"
                      className="link"
                      disabled={busy}
                      onClick={() => setNodeId(node.node_id)}
                    >
                      Use
                    </button>
                  </div>
                  <div className="meta">Last heard {age(node.last_seen_at)}</div>
                </li>
              ))}
            </ul>
          </>
        )}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmedId && trimmedLabel) add(nodeId, label);
          }}
        >
          <div className="settings-field">
            <label htmlFor="tracker-node-id">Node ID</label>
            <input
              id="tracker-node-id"
              placeholder="!a1b2c3d4"
              value={nodeId}
              disabled={busy}
              onChange={(event) => setNodeId(event.target.value)}
            />
          </div>

          <div className="settings-field">
            <label htmlFor="tracker-label">Label</label>
            <div className="settings-actions">
              <input
                id="tracker-label"
                placeholder="Team 2 radio"
                value={label}
                disabled={busy}
                onChange={(event) => setLabel(event.target.value)}
              />
              <button
                type="submit"
                disabled={busy || !trimmedId || !trimmedLabel}
              >
                Add
              </button>
            </div>
          </div>
        </form>
      </section>
    </Modal>
  );
}
