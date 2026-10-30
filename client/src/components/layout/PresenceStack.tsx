import styles from "./PresenceStack.module.css";
import { Avatar } from "../ui";
import { usePresenceStore, type PresenceUser } from "../../store/presence";

export function PresenceStack() {
  const users = usePresenceStore((s) => s.users);

  if (users.length === 0) return null;

  // Sort online users first
  const sorted = [...users].sort((a, b) => {
    if (a.status === "online" && b.status !== "online") return -1;
    if (a.status !== "online" && b.status === "online") return 1;
    return a.name.localeCompare(b.name);
  });

  const displayUsers = sorted.slice(0, 5);
  const overflow = sorted.length - 5;

  const summaryTooltip = sorted
    .map((u) => `${u.name} (${u.status === "online" ? "Online" : "Offline"})`)
    .join("\n");

  return (
    <div className={styles.stack} title={summaryTooltip} aria-label="Branch collaborators">
      {displayUsers.map((u: PresenceUser) => (
        <div key={u.userId} className={styles.avatarWrapper} title={`${u.name} (${u.status})`}>
          <Avatar name={u.name} id={u.userId} size="sm" />
          <span
            className={`${styles.statusDot} ${
              u.status === "online" ? styles.online : styles.offline
            }`}
          />
        </div>
      ))}

      {overflow > 0 && (
        <span className={styles.overflowBadge} title={`${overflow} more collaborators`}>
          +{overflow}
        </span>
      )}
    </div>
  );
}

