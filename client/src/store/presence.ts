import { create } from "zustand";
import type { Role } from "../lib/permissions";

export interface PresenceUser {
  userId: string;
  name: string;
  role: Role;
  status: "online" | "offline";
}

export interface PresenceState {
  users: PresenceUser[];
  setUsers: (users: PresenceUser[]) => void;
  clear: () => void;
}

export const usePresenceStore = create<PresenceState>((set) => ({
  users: [],
  setUsers: (users) => set({ users }),
  clear: () => set({ users: [] }),
}));

