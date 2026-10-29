import { io, Socket } from "socket.io-client";
import { useConnectionStore } from "./connection";
import { useBoardStore } from "../store/board";
import { usePresenceStore } from "../store/presence";
import { useActivityStore } from "../store/activity";
import { useSessionStore } from "../store/session";
import { refresh, getToken } from "../api/http";

let socket: Socket | null = null;
let currentSubscribedBoardId: string | null = null;

export function getSocket(): Socket | null {
  return socket;
}

export function connectSocket(): Socket {
  if (socket) {
    if (!socket.connected) {
      socket.connect();
    }
    return socket;
  }

  socket = io({
    path: "/socket.io",
    auth: (cb) => {
      cb({ token: getToken() });
    },
    reconnection: true,
    reconnectionDelay: 500,
    reconnectionDelayMax: 8000,
    randomizationFactor: 0.5,
  });

  socket.on("connect", () => {
    useConnectionStore.getState().setStatus("connected");
    // Re-subscribe if we had an active board open
    if (currentSubscribedBoardId) {
      subscribeBoard(currentSubscribedBoardId);
    }
  });

  socket.on("disconnect", () => {
    useConnectionStore.getState().setStatus("reconnecting");
  });

  socket.on("connect_error", async (err: Error) => {
    if (err.message === "UNAUTHENTICATED") {
      const refreshed = await refresh();
      if (refreshed && socket) {
        socket.auth = { token: getToken() };
        socket.connect();
      }
    }
  });

  // Task events
  socket.on("task:created", ({ task }: { task: any }) => {
    if (task) useBoardStore.getState().applyServerTask(task);
  });

  socket.on("task:updated", ({ task }: { task: any }) => {
    if (task) useBoardStore.getState().applyServerTask(task);
  });

  socket.on("task:moved", ({ task }: { task: any }) => {
    if (task) useBoardStore.getState().applyServerTask(task);
  });

  socket.on("task:reordered", ({ task }: { task: any }) => {
    if (task) useBoardStore.getState().applyServerTask(task);
  });

  socket.on("task:deleted", ({ taskId, version }: { taskId: string; version?: number }) => {
    if (taskId) useBoardStore.getState().removeTask(taskId, version);
  });

  // Board resync event
  socket.on("board:resync", () => {
    // Board state resync
  });

  // Presence events
  socket.on("presence:update", (data: { users?: any[] }) => {
    if (data?.users) {
      usePresenceStore.getState().setUsers(data.users);
    }
  });

  // Access revoked
  socket.on("access:revoked", (data: { tenantId?: string }) => {
    const activeTenantId = useSessionStore.getState().activeTenantId;
    if (!data.tenantId || data.tenantId === activeTenantId) {
      useSessionStore.getState().logout();
    }
  });

  // Activity stream
  socket.on("activity:created", ({ activity }: { activity: any }) => {
    if (activity) {
      useActivityStore.getState().prependItem(activity);
    }
  });

  return socket;
}

export function subscribeBoard(boardId: string): void {
  currentSubscribedBoardId = boardId;
  if (socket && socket.connected) {
    socket.emit("board:subscribe", { boardId }, () => {});
  }
}

export function unsubscribeBoard(boardId: string): void {
  if (currentSubscribedBoardId === boardId) {
    currentSubscribedBoardId = null;
  }
  if (socket && socket.connected) {
    socket.emit("board:unsubscribe", { boardId }, () => {});
  }
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
    currentSubscribedBoardId = null;
    useConnectionStore.getState().setStatus("offline");
  }
}
