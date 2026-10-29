#!/usr/bin/env node
/**
 * Real-time event watcher utility.
 * Connects to the Kanban Socket.IO server, authenticates, subscribes to a board,
 * and streams real-time events to the terminal.
 *
 * Usage: node scripts/ws-watch.mjs [boardId]
 */

import { io } from "socket.io-client";

const API_BASE = process.env.API_BASE || "http://127.0.0.1:4000/api/v1";
const WS_URL = process.env.WS_URL || "http://127.0.0.1:4000";

async function main() {
  console.log("1. Authenticating as Hyderabad Tenant Admin...");
  const loginRes = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "admin.hyd@northwind.test",
      password: "Passw0rd!",
    }),
  });

  if (!loginRes.ok) {
    console.error("Login failed:", await loginRes.text());
    process.exit(1);
  }

  const { data } = await loginRes.json();
  const token = data.accessToken;
  console.log(`Authenticated as: ${data.user.name} (${data.user.email})`);

  let targetBoardId = process.argv[2];
  if (!targetBoardId) {
    console.log("2. Resolving board ID from workspaces...");
    const wsRes = await fetch(`${API_BASE}/me/workspaces`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const wsData = await wsRes.json();
    const hydTenant = wsData.data[0].tenants.find((t) => t.name === "Hyderabad");
    const boardsRes = await fetch(`${API_BASE}/tenants/${hydTenant.id}/boards`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const boardsData = await boardsRes.json();
    targetBoardId = boardsData.data[0].id;
  }

  console.log(`Target Board ID: ${targetBoardId}`);
  console.log(`Connecting to WebSocket server at ${WS_URL}...`);

  const socket = io(WS_URL, {
    auth: { token },
    transports: ["websocket", "polling"],
  });

  socket.on("connect", () => {
    console.log(`Connected with socket ID: ${socket.id}`);
    console.log(`Subscribing to board: ${targetBoardId}...`);

    socket.emit("board:subscribe", { boardId: targetBoardId }, (ack) => {
      console.log("Subscription Ack:", JSON.stringify(ack, null, 2));
      console.log("Listening for real-time events... Press Ctrl+C to exit.\n");
    });
  });

  socket.on("presence:update", (p) => console.log("[EVENT: presence:update]", JSON.stringify(p)));
  socket.on("task:created", (p) => console.log("[EVENT: task:created]", JSON.stringify(p)));
  socket.on("task:updated", (p) => console.log("[EVENT: task:updated]", JSON.stringify(p)));
  socket.on("task:moved", (p) => console.log("[EVENT: task:moved]", JSON.stringify(p)));
  socket.on("task:reordered", (p) => console.log("[EVENT: task:reordered]", JSON.stringify(p)));
  socket.on("task:deleted", (p) => console.log("[EVENT: task:deleted]", JSON.stringify(p)));
  socket.on("board:updated", (p) => console.log("[EVENT: board:updated]", JSON.stringify(p)));
  socket.on("board:resync", (p) => console.log("[EVENT: board:resync]", JSON.stringify(p)));
  socket.on("access:revoked", (p) => console.log("[EVENT: access:revoked]", JSON.stringify(p)));

  socket.on("connect_error", (err) => {
    console.error("Connection error:", err.message);
  });

  socket.on("disconnect", (reason) => {
    console.log(`Disconnected: ${reason}`);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
