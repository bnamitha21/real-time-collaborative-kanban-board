import { useEffect } from "react";
import styles from "./Toast.module.css";
import { CloseIcon } from "../icons";

export interface ToastProps {
  id?: string;
  message: string;
  variant?: "info" | "warn" | "danger";
  duration?: number;
  onDismiss: () => void;
}

export function Toast({
  message,
  variant = "info",
  duration = 4000,
  onDismiss,
}: ToastProps) {
  useEffect(() => {
    if (duration <= 0) return;
    const timer = setTimeout(() => {
      onDismiss();
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onDismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={`${styles.toast} ${styles[variant]}`}
    >
      <span className={styles.message}>{message}</span>
      <button
        type="button"
        className={styles.closeButton}
        onClick={onDismiss}
        aria-label="Dismiss notification"
      >
        <CloseIcon size={14} />
      </button>
    </div>
  );
}
