import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

type ModalProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  // Extra class on the dialog, so a caller can size it for its own content.
  className?: string;
};

// Built on the native <dialog> so focus trapping, Esc-to-close and the inert
// backdrop come from the platform rather than hand-rolled key handling.
export function Modal({
  open,
  title,
  onClose,
  children,
  className,
}: ModalProps) {
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
      className={className ? `modal ${className}` : "modal"}
      // Fires for Esc and dialog.close() alike, so parent state stays in sync.
      onClose={onClose}
      // The backdrop is part of the dialog element itself; a click landing on
      // the dialog rather than its content means the backdrop was hit.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="modal-header">
        <h2>{title}</h2>
        <button
          type="button"
          className="modal-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
