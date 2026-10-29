import { create } from "zustand";
import type { TaskDto } from "./board";

export type Place = { columnId: string; afterTaskId: string | null };

export type HistoryEntry =
  | {
      kind: "move";
      taskId: string;
      title: string;
      from: Place;
      to: Place;
      versionAfter: number;
    }
  | {
      kind: "update";
      taskId: string;
      title: string;
      before: Record<string, any>;
      after: Record<string, any>;
      versionAfter: number;
    }
  | { kind: "create"; taskId: string; title: string; task: TaskDto }
  | { kind: "delete"; taskId: string; title: string; task: TaskDto };

export interface HistoryState {
  undoStack: HistoryEntry[];
  redoStack: HistoryEntry[];

  record: (entry: HistoryEntry) => void;
  popUndo: () => HistoryEntry | undefined;
  pushUndo: (entry: HistoryEntry) => void;
  popRedo: () => HistoryEntry | undefined;
  pushRedo: (entry: HistoryEntry) => void;
  clear: () => void;
}

export const useHistoryStore = create<HistoryState>((set, get) => ({
  undoStack: [],
  redoStack: [],

  record: (entry) => {
    const { undoStack } = get();
    const next = [...undoStack, entry];
    if (next.length > 50) next.shift();
    set({ undoStack: next, redoStack: [] });
  },

  popUndo: () => {
    const { undoStack } = get();
    if (undoStack.length === 0) return undefined;
    const next = [...undoStack];
    const entry = next.pop();
    set({ undoStack: next });
    return entry;
  },

  pushUndo: (entry) => {
    const { undoStack } = get();
    const next = [...undoStack, entry];
    if (next.length > 50) next.shift();
    set({ undoStack: next });
  },

  popRedo: () => {
    const { redoStack } = get();
    if (redoStack.length === 0) return undefined;
    const next = [...redoStack];
    const entry = next.pop();
    set({ redoStack: next });
    return entry;
  },

  pushRedo: (entry) => {
    const { redoStack } = get();
    const next = [...redoStack, entry];
    if (next.length > 50) next.shift();
    set({ redoStack: next });
  },

  clear: () => set({ undoStack: [], redoStack: [] }),
}));
