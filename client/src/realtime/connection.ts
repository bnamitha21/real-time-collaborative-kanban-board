import { create } from "zustand";

export type ConnectionStatus = "connected" | "reconnecting" | "offline";

export interface ConnectionState {
  status: ConnectionStatus;
  setStatus: (status: ConnectionStatus) => void;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "reconnecting",
  setStatus: (status: ConnectionStatus) => set({ status }),
}));

