import { create } from "zustand";

export interface ActivityItem {
  id: string;
  tenantId: string;
  boardId: string | null;
  taskId: string | null;
  actorId: string | null;
  actorName?: string | null;
  action: string;
  entityType: string;
  entityId: string;
  metadata: {
    title?: string;
    before?: Record<string, any>;
    after?: Record<string, any>;
  };
  createdAt: string;
}

export interface ActivityState {
  items: ActivityItem[];
  nextCursor: string | null;
  loading: boolean;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  setItems: (items: ActivityItem[], nextCursor: string | null) => void;
  prependItem: (item: ActivityItem) => void;
  appendItems: (items: ActivityItem[], nextCursor: string | null) => void;
  clear: () => void;
  setLoading: (l: boolean) => void;
}

export function describeActivity(item: ActivityItem): string {
  const actor = item.actorName || (item.actorId ? "A member" : "A former member");
  const meta = item.metadata || {};
  const title = meta.title || "task";

  switch (item.action) {
    case "task.created":
      return `${actor} created "${title}"`;
    case "task.moved": {
      const fromCol = meta.before?.columnName || meta.before?.columnId || "column";
      const toCol = meta.after?.columnName || meta.after?.columnId || "column";
      return `${actor} moved "${title}" from ${fromCol} to ${toCol}`;
    }
    case "task.reordered":
      return `${actor} reordered "${title}"`;
    case "task.updated": {
      const keys = meta.after ? Object.keys(meta.after) : [];
      if (keys.length === 1 && keys[0] === "description") {
        return `${actor} updated the description of "${title}"`;
      }
      return `${actor} updated "${title}"`;
    }
    case "task.deleted":
      return `${actor} deleted "${title}"`;
    case "board.created":
      return `${actor} created board "${title}"`;
    case "board.deleted":
      return `${actor} deleted board "${title}"`;
    default:
      return `${actor} performed ${item.action}`;
  }
}

export const useActivityStore = create<ActivityState>((set) => ({
  items: [],
  nextCursor: null,
  loading: false,
  isOpen: false,

  setIsOpen: (isOpen) => set({ isOpen }),
  setItems: (items, nextCursor) => set({ items, nextCursor }),
  prependItem: (item) =>
    set((state) => {
      // Prevent duplicates
      if (state.items.some((i) => i.id === item.id)) return state;
      return { items: [item, ...state.items] };
    }),
  appendItems: (newItems, nextCursor) =>
    set((state) => {
      const existingIds = new Set(state.items.map((i) => i.id));
      const filtered = newItems.filter((i) => !existingIds.has(i.id));
      return {
        items: [...state.items, ...filtered],
        nextCursor,
      };
    }),
  clear: () => set({ items: [], nextCursor: null }),
  setLoading: (loading) => set({ loading }),
}));

