import { generateKeyBetween } from "fractional-indexing";
import { http, ApiError } from "../api/http";
import { useBoardStore, type TaskDto } from "./board";
import { useHistoryStore } from "./history";
import { offlineQueue } from "./offlineQueue";
import { useSessionStore } from "./session";

export interface MoveTaskResult {
  success: boolean;
  conflict?: boolean;
  error?: string;
  task?: TaskDto;
}

export function isNetworkError(error: any): boolean {
  return (
    !navigator.onLine ||
    error instanceof TypeError ||
    (error instanceof ApiError && error.status === 0)
  );
}

function getNeighbourPositions(
  order: Record<string, string[]>,
  tasks: Record<string, TaskDto>,
  columnId: string,
  afterTaskId: string | null,
): [string | null, string | null] {
  const colOrder = order[columnId] || [];
  if (colOrder.length === 0) return [null, null];

  if (!afterTaskId) {
    const firstTask = tasks[colOrder[0]];
    return [null, firstTask?.position || null];
  }

  const afterIdx = colOrder.indexOf(afterTaskId);
  if (afterIdx === -1) {
    const lastTask = tasks[colOrder[colOrder.length - 1]];
    return [lastTask?.position || null, null];
  }

  const prevTask = tasks[colOrder[afterIdx]];
  const nextTaskId = colOrder[afterIdx + 1];
  const nextTask = nextTaskId ? tasks[nextTaskId] : null;

  return [prevTask?.position || null, nextTask?.position || null];
}

function getPreviousNeighbour(
  order: Record<string, string[]>,
  columnId: string,
  taskId: string,
): string | null {
  const colOrder = order[columnId] || [];
  const idx = colOrder.indexOf(taskId);
  return idx > 0 ? colOrder[idx - 1] : null;
}

export async function moveTask(
  taskId: string,
  toColumnId: string,
  afterTaskId: string | null,
): Promise<MoveTaskResult> {
  const boardStore = useBoardStore.getState();
  const task = boardStore.tasks[taskId];
  if (!task) return { success: false, error: "Task not found" };

  const session = useSessionStore.getState();
  const userId = session.user?.id || "anonymous";
  const tenantId = session.activeTenantId || "default";

  // Snapshot before move for rollback
  const snapshotTasks = { ...boardStore.tasks };
  const snapshotOrder = { ...boardStore.order };
  const fromColumnId = task.columnId;
  const fromAfterTaskId = getPreviousNeighbour(snapshotOrder, fromColumnId, taskId);

  // Optimistic position
  const [prevPos, nextPos] = getNeighbourPositions(
    snapshotOrder,
    snapshotTasks,
    toColumnId,
    afterTaskId,
  );
  const optimisticPosition = generateKeyBetween(prevPos, nextPos);

  boardStore.moveOptimistic(taskId, toColumnId, optimisticPosition);

  const actionId = crypto.randomUUID();

  try {
    const res = await http.post<{ data: TaskDto }>(`/tasks/${taskId}/move`, {
      toColumnId,
      afterTaskId,
      expectedVersion: task.version,
      actionId,
    });

    const confirmedTask = res.data;
    boardStore.applyServerTask(confirmedTask);

    // Record into Undo history
    useHistoryStore.getState().record({
      kind: "move",
      taskId,
      title: task.title,
      from: { columnId: fromColumnId, afterTaskId: fromAfterTaskId },
      to: { columnId: toColumnId, afterTaskId },
      versionAfter: confirmedTask.version,
    });

    return { success: true, task: confirmedTask };
  } catch (e: any) {
    if (e instanceof ApiError && e.code === "VERSION_CONFLICT") {
      const currentTask = (e.details as any)?.current;
      if (currentTask) {
        boardStore.applyServerTask(currentTask);
      }
      return {
        success: false,
        conflict: true,
        error: "This task was changed by another user. Showing the latest version.",
        task: currentTask,
      };
    } else if (isNetworkError(e)) {
      // Offline fallback
      await offlineQueue.enqueue(userId, tenantId, {
        actionId,
        type: "move",
        taskId,
        baseVersion: task.version,
        payload: { toColumnId, afterTaskId },
        queuedAt: Date.now(),
        status: "pending",
      });
      return {
        success: true,
        error: "You are offline. This change is pending and has not been saved.",
      };
    } else {
      // Rollback on permission/server error
      useBoardStore.setState({ tasks: snapshotTasks, order: snapshotOrder });
      return {
        success: false,
        error: e.message || "Failed to move task",
      };
    }
  }
}

export async function updateTask(
  taskId: string,
  updates: {
    title?: string;
    description?: string;
    priority?: "low" | "medium" | "high";
    assigneeId?: string | null;
    expectedVersion: number;
  },
): Promise<MoveTaskResult> {
  const boardStore = useBoardStore.getState();
  const task = boardStore.tasks[taskId];
  if (!task) return { success: false, error: "Task not found" };

  const session = useSessionStore.getState();
  const userId = session.user?.id || "anonymous";
  const tenantId = session.activeTenantId || "default";

  const beforeValues: Record<string, any> = {
    title: task.title,
    description: task.description,
    priority: task.priority,
    assigneeId: task.assigneeId,
  };

  const actionId = crypto.randomUUID();

  try {
    const res = await http.patch<{ data: TaskDto }>(`/tasks/${taskId}`, {
      ...updates,
      actionId,
    });

    const confirmedTask = res.data;
    boardStore.applyServerTask(confirmedTask);

    useHistoryStore.getState().record({
      kind: "update",
      taskId,
      title: confirmedTask.title,
      before: beforeValues,
      after: updates,
      versionAfter: confirmedTask.version,
    });

    return { success: true, task: confirmedTask };
  } catch (e: any) {
    if (e instanceof ApiError && e.code === "VERSION_CONFLICT") {
      const currentTask = (e.details as any)?.current;
      if (currentTask) boardStore.applyServerTask(currentTask);
      return {
        success: false,
        conflict: true,
        error: "Task conflict detected. Refreshed with latest server version.",
      };
    } else if (isNetworkError(e)) {
      await offlineQueue.enqueue(userId, tenantId, {
        actionId,
        type: "update",
        taskId,
        baseVersion: updates.expectedVersion,
        payload: updates,
        queuedAt: Date.now(),
        status: "pending",
      });
      return {
        success: true,
        error: "You are offline. Update is pending and not saved yet.",
      };
    } else {
      return { success: false, error: e.message || "Failed to update task" };
    }
  }
}

export async function undo(): Promise<{ success: boolean; message: string }> {
  const historyStore = useHistoryStore.getState();
  const entry = historyStore.popUndo();
  if (!entry) return { success: false, message: "Nothing to undo" };

  const boardStore = useBoardStore.getState();

  if (entry.kind === "move") {
    const task = boardStore.tasks[entry.taskId];
    if (!task || task.version !== entry.versionAfter) {
      return {
        success: false,
        message:
          "This change can no longer be undone because the task was changed by someone else.",
      };
    }

    // Run inverse move
    const res = await moveTask(
      entry.taskId,
      entry.from.columnId,
      entry.from.afterTaskId,
    );

    if (res.success && res.task) {
      historyStore.pushRedo({
        ...entry,
        versionAfter: res.task.version,
      });
      return { success: true, message: `Undid move of "${entry.title}"` };
    } else {
      return { success: false, message: res.error || "Undo failed" };
    }
  }

  if (entry.kind === "update") {
    const task = boardStore.tasks[entry.taskId];
    if (!task || task.version !== entry.versionAfter) {
      return {
        success: false,
        message:
          "This change can no longer be undone because the task was changed by someone else.",
      };
    }

    const res = await updateTask(entry.taskId, {
      ...entry.before,
      expectedVersion: task.version,
    });

    if (res.success && res.task) {
      historyStore.pushRedo({
        ...entry,
        versionAfter: res.task.version,
      });
      return { success: true, message: `Undid update of "${entry.title}"` };
    } else {
      return { success: false, message: res.error || "Undo failed" };
    }
  }

  return { success: false, message: "Undo not supported for this action" };
}

export async function redo(): Promise<{ success: boolean; message: string }> {
  const historyStore = useHistoryStore.getState();
  const entry = historyStore.popRedo();
  if (!entry) return { success: false, message: "Nothing to redo" };

  const boardStore = useBoardStore.getState();

  if (entry.kind === "move") {
    const task = boardStore.tasks[entry.taskId];
    if (!task || task.version !== entry.versionAfter) {
      return {
        success: false,
        message:
          "This change can no longer be redone because the task was changed by someone else.",
      };
    }

    const res = await moveTask(
      entry.taskId,
      entry.to.columnId,
      entry.to.afterTaskId,
    );

    if (res.success && res.task) {
      historyStore.record({
        ...entry,
        versionAfter: res.task.version,
      });
      return { success: true, message: `Redid move of "${entry.title}"` };
    } else {
      return { success: false, message: res.error || "Redo failed" };
    }
  }

  if (entry.kind === "update") {
    const task = boardStore.tasks[entry.taskId];
    if (!task || task.version !== entry.versionAfter) {
      return {
        success: false,
        message:
          "This change can no longer be redone because the task was changed by someone else.",
      };
    }

    const res = await updateTask(entry.taskId, {
      ...entry.after,
      expectedVersion: task.version,
    });

    if (res.success && res.task) {
      historyStore.record({
        ...entry,
        versionAfter: res.task.version,
      });
      return { success: true, message: `Redid update of "${entry.title}"` };
    } else {
      return { success: false, message: res.error || "Redo failed" };
    }
  }

  return { success: false, message: "Redo not supported for this action" };
}
