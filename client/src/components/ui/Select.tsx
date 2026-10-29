import { forwardRef, useId, type SelectHTMLAttributes } from "react";
import styles from "./Select.module.css";
import { ChevronDownIcon } from "../icons";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, id, className = "", children, ...props },
  ref,
) {
  const generatedId = useId();
  const selectId = id || generatedId;

  return (
    <div className={styles.container}>
      {label && (
        <label htmlFor={selectId} className={styles.label}>
          {label}
        </label>
      )}
      <div className={styles.selectWrapper}>
        <select ref={ref} id={selectId} className={`${styles.select} ${className}`} {...props}>
          {children}
        </select>
        <span className={styles.icon}>
          <ChevronDownIcon size={14} />
        </span>
      </div>
    </div>
  );
});
