import styles from "./Avatar.module.css";

export interface AvatarProps {
  name: string;
  id?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

function getInitials(name: string): string {
  if (!name.trim()) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function Avatar({ name, id, size = "md", className = "" }: AvatarProps) {
  const seed = id || name || "default";
  const colorIndex = (hashString(seed) % 6) + 1;
  const colorClass = styles[`color${colorIndex}` as keyof typeof styles];
  const initials = getInitials(name);

  return (
    <div
      className={`${styles.avatar} ${styles[size]} ${colorClass} ${className}`}
      title={name}
      aria-label={name}
    >
      {initials}
    </div>
  );
}
