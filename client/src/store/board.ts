import { create } from "zustand";

export interface TaskDto {
  id: string;
  tenantId?: string;
  boardId?: string;
  columnId: string;
  title: string;
  description: string;
  assigneeId: string | null;
  priority: "low" | "medium" | "high";
  position: string;
  version: number;
  pending?: boolean;
  createdBy?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface ColumnDto {
  id: string;
  key: "todo" | "in_progress" | "completed";
  name: string;
  position?: number;
}

export interface Snapshot {
  boardId: string;
  columns: ColumnDto[];
  tasks: TaskDto[];
}

export interface BoardState {
  boardId: string | null;
  columns: ColumnDto[];
  tasks: Record<string, TaskDto>;
  order: Record<string, string[]>; // columnId -> task ids in position order
  loading: boolean;
  error: string | null;

  load: (snapshot: Snapshot) => void;
  applyServerTask: (t: TaskDto) => void;
  removeTask: (id: string, version?: number) => void;
  moveOptimistic: (taskId: string, targetColumnId: string, newPosition: string) => void;
  clear: () => void;
  setLoading: (l: boolean) => void;
  setError: (e: string | null) => void;
}

// Compare two tasks by position COLLATE "C" (lexicographical ASCII), tie-breaking by id
export function compareTasks(a: TaskDto, b: TaskDto): number {
  if (a.position < b.position) return -1;
  if (a.position > b.position) return 1;
  return a.id.localeCompare(b.id);
}

function rebuildOrder(columns: ColumnDto[], tasks: Record<string, TaskDto>): Record<string, string[]> {
  const newOrder: Record<string, string[]> = {};
  for (const col of columns) {
    newOrder[col.id] = [];
  }
  const taskList = Object.values(tasks);
  for (const task of taskList) {
    if (newOrder[task.columnId]) {
      newOrder[task.columnId].push(task.id);
    }
  }
  for (const col of columns) {
    newOrder[col.id].sort((idA, idB) => {
      const a = tasks[idA];
      const b = tasks[idB];
      if (!a || !b) return 0;
      return compareTasks(a, b);
    });
  }
  return newOrder;
}

export const useBoardStore = create<BoardState>((set, get) => ({
  boardId: null,
  columns: [],
  tasks: {},
  order: {},
  loading: false,
  error: null,

  load: ({ boardId, columns, tasks }) => {
    const tasksMap: Record<string, TaskDto> = {};
    for (const t of tasks) {
      tasksMap[t.id] = t;
    }
    const order = rebuildOrder(columns, tasksMap);
    set({
      boardId,
      columns,
      tasks: tasksMap,
      order,
      loading: false,
      error: null,
    });
  },

  applyServerTask: (incoming: TaskDto) => {
    const { tasks, columns } = get();
    const existing = tasks[incoming.id];

    // Reject equal or lower versions to prevent regressing state
    if (existing && incoming.version <= existing.version) {
      return;
    }

    const updatedTasks = {
      ...tasks,
      [incoming.id]: {
        ...incoming,
        pending: false,
      },
    };

    const newOrder = rebuildOrder(columns, updatedTasks);
    set({
      tasks: updatedTasks,
      order: newOrder,
    });
  },

  removeTask: (id: string, _version?: number) => {
    const { tasks, columns } = get();
    if (!tasks[id]) return;

    const updatedTasks = { ...tasks };
    delete updatedTasks[id];

    const newOrder = rebuildOrder(columns, updatedTasks);
    set({
      tasks: updatedTasks,
      order: newOrder,
    });
  },

  moveOptimistic: (taskId: string, targetColumnId: string, newPosition: string) => {
    const { tasks, columns } = get();
    const current = tasks[taskId];
    if (!current) return;

    const updatedTasks = {
      ...tasks,
      [taskId]: {
        ...current,
        columnId: targetColumnId,
        position: newPosition,
        pending: true,
      },
    };

    const newOrder = rebuildOrder(columns, updatedTasks);
    set({
      tasks: updatedTasks,
      order: newOrder,
    });
  },

  clear: () => {
    set({
      boardId: null,
      columns: [],
      tasks: {},
      order: {},
      loading: false,
      error: null,
    });
  },

  setLoading: (loading: boolean) => set({ loading }),
  setError: (error: string | null) => set({ error }),
}));

