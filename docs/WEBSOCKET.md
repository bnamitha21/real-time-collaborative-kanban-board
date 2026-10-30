# Real-Time WebSocket Specification

## Connection & Handshake

- **Transport**: WebSocket / Socket.IO (v4)
- **Path**: `/socket.io`
- **Authentication**: JWT access token provided in the connection auth payload:
  ```ts
  const socket = io({
    path: "/socket.io",
    auth: { token: accessToken }
  });
  ```
- **Error on Invalid/Expired Token**: `UNAUTHENTICATED`. The client attempts silent `/api/v1/auth/refresh` before retrying connection.

---

## Room Scopes & Security Boundary

Rooms are strictly partitioned by organization and branch to eliminate cross-tenant event leakage:

| Room Pattern | Target Audience | Events Broadcast |
|---|---|---|
| `tenant:{tenantId}` | All users active in branch | `presence:update`, `activity:created` |
| `tenant:{tenantId}:board:{boardId}` | Users viewing specific board | `task:created`, `task:updated`, `task:moved`, `task:reordered`, `task:deleted`, `board:resync` |
| `user:{userId}` | Single user | `access:revoked` |

---

## Client-to-Server Events

### `board:subscribe`
Join a specific board room within the authorized branch:
```json
{
  "boardId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
**Ack**: `{ "status": "ok", "boardId": "..." }` or `{ "status": "error", "message": "Access denied" }`

### `board:unsubscribe`
Leave the specified board room:
```json
{
  "boardId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

---

## Server-to-Client Events

### 1. `task:created`
Broadcast to `tenant:{tenantId}:board:{boardId}`:
```json
{
  "task": {
    "id": "uuid",
    "columnId": "uuid",
    "title": "Build Login Page",
    "position": "a0",
    "version": 1
  },
  "actorId": "uuid",
  "actionId": "uuid"
}
```

### 2. `task:moved`
```json
{
  "task": {
    "id": "uuid",
    "columnId": "uuid-in-progress",
    "position": "a0V",
    "version": 2
  },
  "fromColumnId": "uuid-to-do",
  "actorId": "uuid",
  "actionId": "uuid"
}
```

### 3. `task:updated`
```json
{
  "task": {
    "id": "uuid",
    "title": "Updated Title",
    "version": 3
  },
  "actorId": "uuid",
  "actionId": "uuid"
}
```

### 4. `task:deleted`
```json
{
  "taskId": "uuid",
  "version": 4
}
```

### 5. `board:resync`
Instructs clients to re-fetch the complete board snapshot (e.g. after a rebalance operation):
```json
{
  "boardId": "uuid"
}
```

### 6. `presence:update`
Broadcast to `tenant:{tenantId}` on connect, disconnect, or board switch:
```json
{
  "tenantId": "uuid",
  "users": [
    { "userId": "uuid-1", "name": "Priya", "role": "tenant_admin", "status": "online" },
    { "userId": "uuid-2", "name": "Vikram", "role": "member", "status": "offline" }
  ]
}
```

### 7. `access:revoked`
Broadcast to `user:{userId}` when an administrator removes the user from a branch:
```json
{
  "tenantId": "uuid"
}
```
Client immediately clears the board state and drops the socket room.

