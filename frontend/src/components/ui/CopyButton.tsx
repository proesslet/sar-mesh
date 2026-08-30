import { useEffect, useRef, useState } from "react";
import { Button } from "./Button";

const COPIED_FEEDBACK_MS = 1500;

/**
 * Copies a string the operator would otherwise have to retype -- a file path,
 * a project URL.
 *
 * The clipboard API is unavailable over plain HTTP on some browsers, and the
 * app is served over http://127.0.0.1. Failing quietly leaves the text on
 * screen to read, which is the thing that actually matters.
 */
export function CopyButton({
  value,
  label = "Copy",
  title = "Copy to clipboard",
}: {
  value: string;
  label?: string;
  title?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <Button
      variant="link"
      title={title}
      onClick={() => {
        navigator.clipboard
          ?.writeText(value)
          .then(() => {
            setCopied(true);
            timer.current = window.setTimeout(
              () => setCopied(false),
              COPIED_FEEDBACK_MS,
            );
          })
          .catch(() => setCopied(false));
      }}
    >
      {copied ? "Copied" : label}
    </Button>
  );
}
