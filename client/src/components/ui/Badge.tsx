import type { ReactNode } from "react";
import styles from "./Badge.module.css";

export interface BadgeProps {
  variant?: "default" | "primary" | "todo" | "progress" | "done" | "danger" | "warn";
  children: ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[variant]} ${className}`}>
      {children}
    </span>
  );
}
