# Real-Time Collaborative Kanban Board

A production-grade, multi-tenant, real-time collaborative Kanban board built with Python (Flask + Flask-SocketIO), React 18 (TypeScript, Vite, Zustand, @dnd-kit), and PostgreSQL 16.

Inspired by modern, high-density productivity tools (Linear, Notion, Height), it features warm paper aesthetics (`#F5F3EE`), optimistic mutations with automatic rollback, fractional index ordering, live presence indicators, and multi-tenant isolation with database-level Row Level Security (RLS).

---

## 1. Architecture

```
   ┌────────────────────────────────────────────────────────┐
   │                     React 18 SPA                       │
   │  (Zustand Stores, @dnd-kit, Socket.IO Client, IDB)     │
   └───────────▲────────────────────────────────▲───────────┘
               │ HTTP / REST                    │ WebSocket
               │ (JWT In-Memory + Cookie)       │ (/socket.io)
   ┌───────────▼────────────────────────────────▼───────────┐
   │                   Flask Application                    │
   │  - Auth & Sliding Rate Limiter                         │
   │  - Multi-Tenant RBAC Middleware                        │
   │  - OCC Concurrency & Idempotency Manager               │
   │  - Real-time Socket.IO Presence & Scoped Rooms         │
   └───────────▲────────────────────────────────────────────┘
               │ with_tenant(tenant_id)
               │ SET LOCAL app.tenant_id
   ┌───────────▼────────────────────────────────────────────┐
   │                  PostgreSQL 16 Engine                  │
   │  - Composite Foreign Keys (Cross-Tenant Prevention)    │
   │  - Row Level Security (RLS) Policies                   │
   │  - Fractional Index Ordering (COLLATE "C")             │
   └────────────────────────────────────────────────────────┘
```

---

## 2. Tenancy Model

The hierarchy is strictly partitioned into three tiers:
`Organization` ➔ `Tenants (Branches)` ➔ `Boards` ➔ `Columns` ➔ `Tasks`

### Triple-Layer Tenant Defense
1. **Application Route Guards**:
   Middleware resolves tenancy from URL parameters (`tenant_id`, `board_id`, `column_id`, `task_id`). If the user does not have an active membership in the resolved tenant, the API returns `404 Not Found` (never `403`) to prevent leaking existence.
2. **Database Context Isolation**:
   Every database query executes through `with_tenant(tenant_id, fn)`, which executes `SET LOCAL app.tenant_id = '<tenant_id>'` inside the transaction.
3. **Engine-Level Row Level Security (RLS)**:
   Every business table enables PostgreSQL RLS:
   ```sql
   CREATE POLICY tenant_isolation_policy ON tasks
     USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
   ```
   Even if an application query forgets a `WHERE tenant_id = ...` clause, the database engine returns zero rows from other tenants.

---

## 3. Concurrency (Optimistic Concurrency Control)

- **Version Increment**: Every task carries a numeric `version` column starting at 1.
- **Atomic Verification**:
  Modifications require `expectedVersion`. The server performs:
  ```sql
  SELECT id, version, column_id FROM tasks WHERE id = %s FOR UPDATE;
  ```
  If `task.version != expected_version`, the server immediately aborts with HTTP `409 Conflict` and code `VERSION_CONFLICT`, returning the current authoritative state in `details.current`.
- **Idempotency Keys**:
  Mutations accept a unique `actionId` UUID stored in `processed_actions`. If a network disconnect causes the client to replay an already executed action, the server returns the cached response without re-executing writes or generating duplicate activity entries.

---

## 4. Fractional Index Ordering

Tasks are sorted within columns using variable-length fractional index strings (`position text COLLATE "C"`):
- Moving a card computes midpoint keys between neighbors (e.g. between `"a0"` and `"a1"` ➔ `"a0V"`).
- Updating a position modifies only the single affected row.
- **Rebalance Safeguard**: If repeated insertions cause a key length to exceed 64 bytes, a background transaction locks the column and rebalances keys evenly (`"a0"`, `"a1"`, `"a2"...`) and emits `board:resync`.

---

## 5. Real-Time & Socket.IO Rooms

- **Connection & Auth**: The client establishes a WebSocket connection passing its in-memory JWT.
- **Tenant-Scoped Rooms**:
  - `tenant:{id}`: Broadcasts branch presence updates and activity logs.
  - `tenant:{id}:board:{id}`: Broadcasts task creates, updates, moves, and deletions.
  - `user:{id}`: Delivers security events such as `access:revoked`.
- **Zero Cross-Tenant Leakage**: Socket connections are joined only to rooms matching the authenticated user's active tenant permissions.

---

## 6. Undo & Redo System

- **Stack Limit**: Stores up to 50 reversible actions in memory.
- **Version Validation**: Before running an inverse action (e.g. moving a task back to its previous column), the client verifies that `task.version == versionAfter`. If another collaborator modified the task in the interim, undo is refused with a warning banner: *"This change can no longer be undone because the task was changed by someone else."*
- **Neighbour Fallback**: If the former preceding card was deleted or moved, the restored card safely falls back to the top of the column.

---

## 7. Network Recovery & Offline Support

- **Connection State Machine**: Reacts to `connected ➔ reconnecting ➔ offline`.
- **IndexedDB Queue**: Supported actions (create, edit, move, delete) are enqueued in IndexedDB (`idb-keyval`).
- **Coalescing**: Consecutive moves of the same card are collapsed into a single operation preserving the initial `baseVersion`.
- **Recovery Sequence**:
  1. Socket reconnects (silent token refresh if expired).
  2. Re-subscribes to board room.
  3. Re-fetches fresh board snapshot from `/boards/:id`.
  4. Replays queued actions in order using original idempotency keys.
  5. Displays recovery summary toast with conflicting actions available for review.

---

## 8. Trade-Offs & Limitations

- **Deleted Task Undo**: Recreating a deleted task through Undo generates a **new** task UUID with version 1 at the former position rather than resurrecting the old row. This ensures immutable audit trails.
- **Fractional Index Rebalancing**: Rebalancing locks the specific column briefly with `SELECT ... FOR UPDATE` to re-assign positions. This is acceptable given the rare frequency (only when key lengths exceed 64 characters).

---

## 9. Running Locally

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16 (local or Docker)

### 1. Start PostgreSQL
```bash
docker run --name kanban-pg -e POSTGRES_USER=owner -e POSTGRES_PASSWORD=owner_pw -e POSTGRES_DB=kanban -p 5432:5432 -d postgres:16-alpine
```

### 2. Configure Environment
Create `.env` in the root:
```env
DATABASE_URL_OWNER=postgresql://owner:owner_pw@localhost:5432/kanban
DATABASE_URL=postgresql://kanban_app:app_pw@localhost:5432/kanban
JWT_ACCESS_SECRET=super_secret_access_key_12345
JWT_REFRESH_SECRET=super_secret_refresh_key_12345
FLASK_ENV=development
PORT=4000
```

### 3. Run Migrations & Seed Data
```bash
python -m server.src.db.migrate
python -m server.src.db.seed
```

### 4. Start Development Servers
```bash
# Terminal 1: Backend server (port 4000)
npm run dev:server

# Terminal 2: Frontend client (port 5173)
npm run dev:client
```
Navigate to: **`http://localhost:5173/`**

---

## 10. Seed Accounts & Roles

| Role | Email | Password | Scope |
|---|---|---|---|
| **Org Admin** | `orgadmin@northwind.test` | `Passw0rd!` | All branches in Northwind |
| **Tenant Admin** | `admin.hyd@northwind.test` | `Passw0rd!` | Hyderabad branch administrator |
| **Member** | `member.hyd@northwind.test` | `Passw0rd!` | Hyderabad branch member |
| **Multi-Branch Member** | `multi@northwind.test` | `Passw0rd!` | Member in Hyderabad & Vijayawada |

---

## 11. Security Checklist

- [x] Passwords hashed with Argon2id (memoryCost: 65536, timeCost: 3).
- [x] JWT access tokens kept only in memory (15m TTL).
- [x] Rotating refresh tokens in `HttpOnly`, `SameSite=Lax` cookies.
- [x] Sliding-window rate limiting on sensitive routes.
- [x] Database Row Level Security (RLS) active on all business tables.
- [x] Composite foreign keys preventing cross-tenant references.
- [x] Zero hardcoded colors outside `client/src/styles/tokens.css`.
- [x] Production Docker containers execute as unprivileged non-root users.

---

## 12. Testing

All test code (`server/tests/` and `client/tests/`) is maintained locally and strictly excluded from git tracking via `.gitignore`.

Run the test suites locally:
```bash
# Backend pytest suite (51 tests)
pytest server/tests

# Backend linting & static types
ruff check server
mypy server/src

# Frontend Vitest suite (39 tests)
npm test -w client

# Frontend type checking
npm run typecheck -w client
```
