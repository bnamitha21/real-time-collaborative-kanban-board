import { get, set, del } from "idb-keyval";

export interface QueuedAction {
  actionId: string;
  type: "move" | "update" | "create" | "delete";
  taskId?: string;
  baseVersion: number;
  payload: any;
  queuedAt: number;
  status: "pending" | "conflict" | "failed";
}

const memoryFallback = new Map<string, QueuedAction[]>();

const hasIndexedDB = typeof indexedDB !== "undefined";

function storageKey(userId: string, tenantId: string): string {
  return `kanban_queue_${userId}_${tenantId}`;
}

export const offlineQueue = {
  async list(userId: string, tenantId: string): Promise<QueuedAction[]> {
    const key = storageKey(userId, tenantId);
    if (!hasIndexedDB) {
      return memoryFallback.get(key) || [];
    }
    try {
      const items = await get<QueuedAction[]>(key);
      return items || [];
    } catch {
      return memoryFallback.get(key) || [];
    }
  },

  async enqueue(
    userId: string,
    tenantId: string,
    action: QueuedAction,
  ): Promise<QueuedAction[]> {
    const key = storageKey(userId, tenantId);
    const list = await this.list(userId, tenantId);

    // Coalescing (15.7): consecutive queued moves of the same task collapse into one
    if (action.type === "move" && action.taskId) {
      const last = list[list.length - 1];
      if (last && last.type === "move" && last.taskId === action.taskId) {
        last.payload = action.payload;
        last.actionId = action.actionId;
        last.queuedAt = action.queuedAt;
        if (hasIndexedDB) {
          try {
            await set(key, list);
          } catch {
            memoryFallback.set(key, list);
          }
        } else {
          memoryFallback.set(key, list);
        }
        return list;
      }
    }

    list.push(action);
    if (hasIndexedDB) {
      try {
        await set(key, list);
      } catch {
        memoryFallback.set(key, list);
      }
    } else {
      memoryFallback.set(key, list);
    }
    return list;
  },

  async remove(userId: string, tenantId: string, actionId: string): Promise<void> {
    const key = storageKey(userId, tenantId);
    const list = await this.list(userId, tenantId);
    const updated = list.filter((item) => item.actionId !== actionId);
    if (hasIndexedDB) {
      try {
        await set(key, updated);
      } catch {
        memoryFallback.set(key, updated);
      }
    } else {
      memoryFallback.set(key, updated);
    }
  },

  async clear(userId: string, tenantId: string): Promise<void> {
    const key = storageKey(userId, tenantId);
    memoryFallback.delete(key);
    if (hasIndexedDB) {
      try {
        await del(key);
      } catch {
        // ignore
      }
    }
  },
};
