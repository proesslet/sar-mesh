import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./Modal.module.css";

// Built on the native <dialog> so focus trapping, Esc-to-close and the inert
// backdrop come from the platform rather than hand-rolled key handling.
export function Modal({
  open,
  title,
  onClose,
  size = "sm",
  flush,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  /** "md" for a list of records, "lg" for content beside its own navigation. */
  size?: "sm" | "md" | "lg";
  /**
   * Drop the body's padding and scrolling, for content that lays out its own
   * panes. The content is then responsible for scrolling whatever should
   * scroll, and for its own padding.
   */
  flush?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={cx(styles.modal, styles[size])}
      // Fires for Esc and dialog.close() alike, so parent state stays in sync.
      onClose={onClose}
      // The backdrop is part of the dialog element itself; a click landing on
      // the dialog rather than its content means the backdrop was hit.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className={styles.header}>
        <h2>{title}</h2>
        <button
          type="button"
          className={styles.close}
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
      </div>
      <div className={cx(styles.body, flush && styles.flush)}>{children}</div>
    </dialog>
  );
}
