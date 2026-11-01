# REST API Specification (v1)

Base URL: `/api/v1`

All requests except authentication endpoints require an `Authorization: Bearer <accessToken>` header.
Cookies: Refresh tokens are issued as HTTP-only secure cookies (`refresh`) on `/api/v1/auth`.

---

## 1. Authentication (`/auth`)

### `POST /auth/register`
- **Permission**: Public (rate limited: 10/min)
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "name": "Alex Smith",
    "password": "Passw0rdStrong!"
  }
  ```
- **Response** (201 Created):
  ```json
  {
    "data": {
      "id": "c1f7a112-...",
      "email": "user@example.com",
      "name": "Alex Smith",
      "createdAt": "2026-10-29T10:00:00Z"
    }
  }
  ```

### `POST /auth/login`
- **Permission**: Public (rate limited: 10/min)
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "Passw0rdStrong!"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "data": {
      "accessToken": "eyJhbGciOi...",
      "user": {
        "id": "c1f7a112-...",
        "email": "user@example.com",
        "name": "Alex Smith"
      }
    }
  }
  ```
- **Sets Cookie**: `refresh=<token>; HttpOnly; SameSite=Lax; Path=/api/v1/auth`

### `POST /auth/refresh`
- **Permission**: Public (requires valid `refresh` cookie)
- **Response** (200 OK):
  ```json
  {
    "data": {
      "accessToken": "eyJhbGciOi...",
      "user": { ... }
    }
  }
  ```

### `POST /auth/logout`
- **Permission**: Public
- **Response** (200 OK):
  ```json
  {
    "data": { "success": true }
  }
  ```

---

## 2. Workspaces & Tenancy (`/me`)

### `GET /me/workspaces`
- **Permission**: Authenticated
- **Response** (200 OK):
  ```json
  {
    "data": [
      {
        "organization": { "id": "uuid", "name": "Northwind Traders" },
        "role": "org_admin",
        "tenants": [
          { "id": "uuid-1", "name": "Hyderabad", "role": "org_admin" },
          { "id": "uuid-2", "name": "Vijayawada", "role": "org_admin" }
        ]
      }
    ]
  }
  ```

---

## 3. Organizations (`/organizations`)

### `GET /organizations`
- **Permission**: Authenticated
- **Response**: List of user organizations.

### `GET /organizations/:orgId`
- **Permission**: `org.read`

### `PATCH /organizations/:orgId`
- **Permission**: `org.update` (Org Admin only)
- **Body**: `{ "name": "Updated Corp Name" }`

### `DELETE /organizations/:orgId`
- **Permission**: `org.delete` (Org Admin only)

---

## 4. Branches / Tenants (`/tenants`)

### `POST /organizations/:orgId/tenants`
- **Permission**: `tenant.create` (Org Admin only)
- **Body**: `{ "name": "Chennai" }`

### `GET /tenants/:tenantId`
- **Permission**: `tenant.read`

### `GET /tenants/:tenantId/members`
- **Permission**: `tenant.read`
- **Response**: `[ { "id": "...", "name": "...", "email": "...", "role": "..." } ]`

### `POST /tenants/:tenantId/members`
- **Permission**: `tenant_admin` or `org_admin`
- **Body**: `{ "email": "user@northwind.test", "role": "member" }`

### `DELETE /tenants/:tenantId/members/:userId`
- **Permission**: `tenant_admin` (member only) or `org_admin` (any)

---

## 5. Boards (`/tenants/:tenantId/boards`)

### `GET /tenants/:tenantId/boards`
- **Permission**: `board.read`

### `POST /tenants/:tenantId/boards`
- **Permission**: `board.create` (Org Admin / Tenant Admin)
- **Body**: `{ "name": "Q4 Sprint Board" }`
- Automatically seeds exactly 3 columns: `To Do` (pos 1), `In Progress` (pos 2), `Completed` (pos 3).

### `GET /tenants/:tenantId/boards/:boardId`
- **Permission**: `board.read`

### `PATCH /tenants/:tenantId/boards/:boardId`
- **Permission**: `board.update`

### `DELETE /tenants/:tenantId/boards/:boardId`
- **Permission**: `board.delete`

---

## 6. Columns (`/tenants/:tenantId/boards/:boardId/columns`)

### `GET /tenants/:tenantId/boards/:boardId/columns`
- **Permission**: `board.read`

### `PATCH /columns/:columnId`
- **Permission**: `column.rename` (Admins only; key is immutable)
- **Body**: `{ "name": "Up Next" }`

---

## 7. Tasks (`/tenants/:tenantId/boards/:boardId/tasks` and `/tasks`)

### `GET /tenants/:tenantId/boards/:boardId/tasks`
- **Permission**: `task.read`
- Returns tasks ordered by `position COLLATE "C" ASC`.

### `POST /boards/:boardId/tasks` (or `/tenants/:tenantId/boards/:boardId/tasks`)
- **Permission**: `task.create` (Admins only)
- **Body**:
  ```json
  {
    "columnId": "uuid",
    "title": "Build User Profile",
    "description": "Optional markdown details",
    "priority": "medium",
    "assigneeId": "uuid | null",
    "actionId": "optional-idempotency-uuid"
  }
  ```

### `GET /tasks/:taskId`
- **Permission**: `task.read`

### `PATCH /tasks/:taskId`
- **Permission**: `task.update` (Admins any; Members only if assigned)
- **Body**:
  ```json
  {
    "expectedVersion": 2,
    "title": "New Title",
    "description": "Updated description",
    "priority": "high",
    "assigneeId": "uuid",
    "actionId": "uuid"
  }
  ```
- **OCC Error** (409 Conflict):
  ```json
  {
    "error": {
      "code": "VERSION_CONFLICT",
      "message": "Task has been updated by another user.",
      "details": {
        "current": { ... }
      }
    }
  }
  ```

### `POST /tasks/:taskId/move`
- **Permission**: `task.move` (Admins any; Members only if assigned)
- **Body**:
  ```json
  {
    "expectedVersion": 2,
    "toColumnId": "uuid-col-progress",
    "afterTaskId": "uuid-previous-task | null",
    "actionId": "uuid-required"
  }
  ```
- **OCC Error** (409 Conflict): returns authoritative `current` task payload.

### `DELETE /tasks/:taskId`
- **Permission**: `task.delete` (Admins only)

---

## 8. Activity Logs (`/tenants/:tenantId/activity`)

### `GET /tenants/:tenantId/activity`
- **Permission**: `activity.read`
- **Query params**:
  - `boardId`: filter to specific board
  - `taskId`: filter to specific task
  - `cursor`: keyset pagination cursor
  - `limit`: items per page (default 50, max 100)
- **Response**:
  ```json
  {
    "data": [
      {
        "id": "12",
        "actorId": "uuid",
        "actorName": "Priya",
        "action": "task.moved",
        "before": { "columnName": "To Do" },
        "after": { "columnName": "In Progress" },
        "createdAt": "2026-10-29T10:00:00Z"
      }
    ],
    "nextCursor": "string | null"
  }
  ```



---

## 9. Example cURL Workflows

### 9.1 Login
```bash
curl -X POST http://localhost:4000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email": "admin.hyd@northwind.test", "password": "Passw0rd!"}'
```

### 9.2 Fetch Workspaces & Active Tenant
```bash
curl -X GET http://localhost:4000/api/v1/me/workspaces \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 9.3 List Boards for Tenant
```bash
curl -X GET http://localhost:4000/api/v1/tenants/<TENANT_ID>/boards \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 9.4 Create a Task
```bash
curl -X POST http://localhost:4000/api/v1/tenants/<TENANT_ID>/boards/<BOARD_ID>/tasks \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "columnId": "<COLUMN_ID>",
    "title": "Design Database Schema",
    "description": "PostgreSQL 16 with RLS policies",
    "priority": "high"
  }'
```

### 9.5 Move a Task (OCC Protected)
```bash
curl -X POST http://localhost:4000/api/v1/tasks/<TASK_ID>/move \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "expectedVersion": 1,
    "toColumnId": "<NEW_COLUMN_ID>",
    "afterTaskId": null,
    "actionId": "c9bf9e57-1685-4c89-bafb-ff5af830be8a"
  }'
```

### 9.6 View Tenant Activity Audit Log
```bash
curl -X GET "http://localhost:4000/api/v1/tenants/<TENANT_ID>/activity?limit=20" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
