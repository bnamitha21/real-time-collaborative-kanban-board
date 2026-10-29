import { useEffect } from "react";
import styles from "./ActivityDrawer.module.css";
import { Drawer, Avatar, Button, Spinner } from "../ui";
import { useActivityStore, describeActivity } from "../../store/activity";
import { useSessionStore } from "../../store/session";
import { http } from "../../api/http";

export function ActivityDrawer() {
  const { items, nextCursor, loading, isOpen, setIsOpen, appendItems, setItems, setLoading } =
    useActivityStore();
  const activeTenantId = useSessionStore((s) => s.activeTenantId);

  useEffect(() => {
    if (!isOpen || !activeTenantId) return;

    const fetchInitialActivity = async () => {
      setLoading(true);
      try {
        const res = await http.get<{ data: any[]; nextCursor: string | null }>(
          `/tenants/${activeTenantId}/activity?limit=25`,
        );
        setItems(res.data || [], res.nextCursor || null);
      } catch {
        setItems([], null);
      } finally {
        setLoading(false);
      }
    };

    fetchInitialActivity();
  }, [isOpen, activeTenantId, setItems, setLoading]);

  const loadMore = async () => {
    if (!nextCursor || !activeTenantId || loading) return;
    setLoading(true);
    try {
      const res = await http.get<{ data: any[]; nextCursor: string | null }>(
        `/tenants/${activeTenantId}/activity?cursor=${encodeURIComponent(
          nextCursor,
        )}&limit=25`,
      );
      appendItems(res.data || [], res.nextCursor || null);
    } finally {
      setLoading(false);
    }
  };

  const formatRelativeTime = (isoString: string): string => {
    try {
      const diffSec = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
      if (diffSec < 60) return "just now";
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
      return `${Math.floor(diffSec / 86400)}d ago`;
    } catch {
      return isoString;
    }
  };

  return (
    <Drawer
      open={isOpen}
      title="Branch Activity"
      onClose={() => setIsOpen(false)}
      footer={
        nextCursor ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={loadMore}
            disabled={loading}
          >
            {loading ? "Loading…" : "Load more"}
          </Button>
        ) : null
      }
    >
      {loading && items.length === 0 ? (
        <div className={styles.emptyState}>
          <Spinner size="md" />
        </div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>No activity recorded yet.</div>
      ) : (
        <div className={styles.activityList}>
          {items.map((item) => (
            <div key={item.id} className={styles.activityItem}>
              <Avatar
                name={item.actorName || "Member"}
                id={item.actorId || undefined}
                size="sm"
              />
              <div className={styles.itemContent}>
                <p className={styles.sentence}>{describeActivity(item)}</p>
                <time
                  className={styles.timestamp}
                  dateTime={item.createdAt}
                  title={new Date(item.createdAt).toLocaleString()}
                >
                  {formatRelativeTime(item.createdAt)}
                </time>
              </div>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  );
}
