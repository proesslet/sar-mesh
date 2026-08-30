import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./Modal.module.css";

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
  size?: "sm" | "md" | "lg";
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
      onClose={onClose}
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
