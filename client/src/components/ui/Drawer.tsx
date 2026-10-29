import { useEffect, useRef, type ReactNode } from "react";
import styles from "./Drawer.module.css";
import { CloseIcon } from "../icons";

export interface DrawerProps {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  actions?: ReactNode;
}

export function Drawer({
  open,
  title,
  onClose,
  children,
  footer,
  actions,
}: DrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    previouslyFocusedRef.current = document.activeElement as HTMLElement;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    // Initial focus on open: do not steal focus if already inside
    const container = drawerRef.current;
    if (container && !container.contains(document.activeElement)) {
      const preferred = container.querySelector<HTMLElement>(
        '[autofocus], input:not([disabled]), textarea:not([disabled]), select:not([disabled])',
      );
      if (preferred) {
        preferred.focus();
      } else {
        const focusable = container.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          container.focus();
        }
      }
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocusedRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className={styles.backdrop} onClick={onClose} aria-hidden="true" />
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : "Detail panel"}
        className={styles.drawer}
        tabIndex={-1}
      >
        <div className={styles.header}>
          <div className={styles.title}>{title}</div>
          <div className={styles.headerActions}>
            {actions}
            <button
              type="button"
              className={styles.closeButton}
              onClick={onClose}
              aria-label="Close drawer"
            >
              <CloseIcon size={16} />
            </button>
          </div>
        </div>
        <div className={styles.body}>{children}</div>
        {footer && <div className={styles.footer}>{footer}</div>}
      </aside>
    </>
  );
}
