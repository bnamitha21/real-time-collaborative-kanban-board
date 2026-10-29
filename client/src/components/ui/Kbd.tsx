import type { ReactNode } from "react";
import styles from "./Kbd.module.css";

export interface KbdProps {
  children: ReactNode;
  className?: string;
}

export function Kbd({ children, className = "" }: KbdProps) {
  return <kbd className={`${styles.kbd} ${className}`}>{children}</kbd>;
}
