import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { Diagnostics, FileLocation, LogTail } from "../../api";
import {
  Actions,
  Button,
  CopyButton,
  ErrorMessage,
  Message,
  Meta,
  Name,
  Row,
  Section,
} from "../../components/ui";
import { toMessage } from "../../lib/errors";
import styles from "./SettingsDiagnostics.module.css";

const LOG_LINES = 200;

function Location({
  title,
  file,
}: {
  title: string;
  file: FileLocation | null;
}) {
  if (file === null) return null;

  return (
    <div className={styles.location}>
      <Row>
        <Name>{title}</Name>
        <CopyButton value={file.path} />
      </Row>
      <code className={styles.path}>{file.path}</code>
      {!file.exists && <Meta>Not created yet</Meta>}
    </div>
  );
}

export function SettingsDiagnostics({
  diagnostics,
  error: loadError,
}: {
  // Fetched once for the whole dialog, since About reports the version from
  // the same request.
  diagnostics: Diagnostics | null;
  error: string | null;
}) {
  const [log, setLog] = useState<LogTail | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const outputRef = useRef<HTMLPreElement>(null);

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
        .catch((cause) => setLogError(toMessage(cause)));
    }
  }

  return (
    <Section title="Files">
      <ErrorMessage error={loadError ?? logError} />

      <Location title="Database" file={diagnostics?.database ?? null} />
      <Location title="Log" file={diagnostics?.log ?? null} />
      <Location title="Map packs" file={diagnostics?.basemap_dir ?? null} />

      <Actions>
        <Button onClick={toggleLog}>{showLog ? "Hide log" : "View log"}</Button>
      </Actions>

      {showLog && (
        <div ref={logRef}>
          {log && log.lines.length > 0 ? (
            <pre className={styles.log} ref={outputRef}>
              {log.lines.join("\n")}
            </pre>
          ) : (
            <Message tone="empty">Nothing logged yet.</Message>
          )}
        </div>
      )}
    </Section>
  );
}
