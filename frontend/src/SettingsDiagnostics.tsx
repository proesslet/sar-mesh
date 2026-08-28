import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Diagnostics, FileLocation, LogTail } from "./api";

const LOG_LINES = 200;

function CopyPath({ path }: { path: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      className="link"
      title="Copy to clipboard"
      onClick={() => {
        // Unavailable over plain HTTP on some browsers, and the app is served
        // over http://127.0.0.1. Failing quietly leaves the path on screen to
        // read, which is the thing that actually matters.
        navigator.clipboard
          ?.writeText(path)
          .then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          })
          .catch(() => setCopied(false));
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function Location({ title, file }: { title: string; file: FileLocation | null }) {
  if (file === null) return null;

  return (
    <div className="location">
      <div className="tracker-row">
        <span className="label">{title}</span>
        <CopyPath path={file.path} />
      </div>
      <code className="path">{file.path}</code>
      {!file.exists && <span className="meta">Not created yet</span>}
    </div>
  );
}

export function SettingsDiagnostics() {
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [log, setLog] = useState<LogTail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const outputRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    api
      .diagnostics()
      .then(setDiagnostics)
      .catch((cause) => setError(String(cause)));
  }, []);

  // The log opens at the bottom of a modal that is already scrolled to its
  // top, so without this the operator clicks "View log" and nothing appears to
  // happen -- the output landed below the fold.
  useEffect(() => {
    if (!showLog || !log) return;

    logRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });

    // The tail reads oldest-first, but whatever just went wrong is the last
    // line, so the block starts scrolled to the end.
    const output = outputRef.current;
    if (output) output.scrollTop = output.scrollHeight;
  }, [showLog, log]);

  function toggleLog() {
    const next = !showLog;
    setShowLog(next);

    // Refetched on each open so the panel shows the log as it is now, not as
    // it was when settings were first opened.
    if (next) {
      api
        .log(LOG_LINES)
        .then(setLog)
        .catch((cause) => setError(String(cause)));
    }
  }

  return (
    <section className="settings-section">
      <h3>Files</h3>

      {error && <p className="error">{error}</p>}

      <Location title="Database" file={diagnostics?.database ?? null} />
      <Location title="Log" file={diagnostics?.log ?? null} />
      <Location title="Map packs" file={diagnostics?.basemap_dir ?? null} />

      <div className="settings-actions">
        <button type="button" onClick={toggleLog}>
          {showLog ? "Hide log" : "View log"}
        </button>
      </div>

      {showLog && (
        <div ref={logRef}>
          {log && log.lines.length > 0 ? (
            <pre className="log" ref={outputRef}>
              {log.lines.join("\n")}
            </pre>
          ) : (
            <p className="empty">Nothing logged yet.</p>
          )}
        </div>
      )}
    </section>
  );
}
