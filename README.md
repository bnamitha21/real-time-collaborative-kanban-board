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
- PostgreSQL 16 (Local service running on port 5432) & pgAdmin 4

### 1. Database Setup & Control
The project runs natively against local PostgreSQL 16 (no Docker required).

```powershell
# Check status of local PostgreSQL service
npm run db:status

# Initialize database, create roles, run migrations & seed data
npm run db:setup
# (or: python scripts/init_db.py --seed)
```

You can view all databases, tables, and roles visually using **pgAdmin 4** (installed with PostgreSQL).

### 2. Start Development Servers
```bash
# Terminal 1: Backend server (port 4000)
npm run dev:server

# Terminal 2: Frontend client (port 5173)
npm run dev:client
```
Navigate to: **`http://localhost:5173/`**

---

## 10. Environment Variables

Create or verify `.env` in the root directory:

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL_OWNER` | `postgresql://owner:owner_pw@localhost:5432/kanban` | DSN for schema migrations & seed (bypasses RLS) |
| `DATABASE_URL` | `postgresql://kanban_app:app_pw@localhost:5432/kanban` | Application queries role (PostgreSQL RLS enforced) |
| `JWT_ACCESS_SECRET` | *(32+ char secret)* | Secret key for signing in-memory access tokens |
| `JWT_ACCESS_TTL_SECONDS` | `900` (15 min) | Access token lifespan |
| `REFRESH_TTL_DAYS` | `14` | Refresh token lifespan in HttpOnly cookie |
| `FLASK_ENV` | `development` | Flask runtime environment |
| `PORT` | `4000` | Backend server port |
| `CLIENT_ORIGIN` | `http://localhost:5173` | Allowed CORS origin |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 11. Project Structure

```
kanban/
├── client/                     # React 18 TypeScript Frontend
│   ├── src/
│   │   ├── api/                # HTTP & Axios client with auto-refresh
│   │   ├── components/         # Board, Column, TaskCard, Dialogs, UI components
│   │   ├── lib/                # Permissions, types, fractional index helpers
│   │   ├── pages/              # LoginPage, BoardPage
│   │   ├── realtime/           # Socket.IO connection and event dispatchers
│   │   ├── store/              # Zustand state stores (board, session, offlineQueue)
│   │   └── styles/             # Design tokens and CSS modules
│   └── package.json
├── server/                     # Flask Backend Application
│   ├── migrations/             # Idempotent raw SQL migration scripts
│   │   ├── 001_init.sql        # Core relational tables & constraints
│   │   ├── 002_rls.sql         # Row Level Security policies & kanban_app role
│   │   ├── 003_scope_fns.sql   # Security definer helper functions
│   │   └── 004_column_scope.sql# Column security function
│   ├── src/
│   │   ├── config/             # Environment validation with Pydantic
│   │   ├── db/                 # psycopg3 connection pool & migration runner
│   │   ├── middleware/         # Auth, RLS tenancy, rate limiting, validation
│   │   ├── modules/            # Auth, Organizations, Tenants, Boards, Columns, Tasks, Activity
│   │   ├── realtime/           # Socket.IO rooms, presence, event publishers
│   │   ├── app.py              # Flask application factory
│   │   └── main.py             # Server entrypoint with auto-migration
│   └── requirements.txt
├── docs/                       # Project Documentation
│   ├── API.md                  # Complete REST API specification with cURL examples
│   ├── DATABASE_SETUP.md       # PostgreSQL & pgAdmin setup instructions
│   ├── DECISIONS.md            # Architecture Decision Records (ADRs)
│   ├── ER.md                   # Entity-Relationship diagram & composite FK details
│   ├── er-diagram.svg          # Visual SVG export of the ER diagram
│   └── WEBSOCKET.md            # Socket.IO real-time protocol specification
├── scripts/                    # Automation & Maintenance Scripts
│   ├── init_db.py              # Cross-platform DB initializer & RLS verifier
│   ├── setup_db.ps1            # Windows PostgreSQL setup helper
│   ├── start_db.ps1            # Start local PostgreSQL service
│   ├── stop_db.ps1             # Stop local PostgreSQL service
│   ├── status_db.ps1           # Check local PostgreSQL status
│   └── smoke.ps1               # Automated end-to-end smoke test
├── package.json                # Monorepo scripts (db:start, dev:server, dev:client)
└── README.md                   # Comprehensive project documentation
```

---

## 12. Seed Accounts & Roles

All accounts are pre-seeded with password: **`Passw0rd!`**

| Role | Email | Password | Scope |
|---|---|---|---|
| **Org Admin** | `orgadmin@northwind.test` | `Passw0rd!` | All branches in Northwind Traders |
| **Tenant Admin** | `admin.hyd@northwind.test` | `Passw0rd!` | Hyderabad branch administrator |
| **Member** | `member.hyd@northwind.test` | `Passw0rd!` | Hyderabad branch member |
| **Member 2** | `member2.hyd@northwind.test` | `Passw0rd!` | Hyderabad branch member |
| **Tenant Admin (VJA)** | `admin.vja@northwind.test` | `Passw0rd!` | Vijayawada branch administrator |
| **Org Admin (Contoso)** | `admin@contoso.test` | `Passw0rd!` | Contoso Retail administrator |
| **Multi-Branch Member** | `multi@northwind.test` | `Passw0rd!` | Member in Hyderabad & Vijayawada |

---

## 13. Security Checklist

- [x] Passwords hashed with Argon2id (`argon2-cffi`).
- [x] JWT access tokens kept strictly in memory (15m TTL).
- [x] Rotating refresh tokens in `HttpOnly`, `SameSite=Lax` cookies.
- [x] Sliding-window rate limiting on sensitive routes.
- [x] Database Row Level Security (RLS) active on all business tables.
- [x] Composite foreign keys preventing cross-tenant references.
- [x] Zero hardcoded colors outside `client/src/styles/tokens.css`.
- [x] Database application queries execute under restricted non-owner role (`kanban_app`) with RLS.
- [x] Strict 404-not-403 tenant discovery prevention.

---

## 14. Testing

All test code (`server/tests/` and `client/tests/`) is maintained locally and strictly excluded from git tracking via `.gitignore`.

Run the test suites locally:
```bash
# Backend pytest suite (51 tests)
pytest server/tests

# Backend static types & lint
mypy server/src
ruff check server

# Frontend Vitest suite (39 tests)
npm test -w client

# Frontend type checking & build
npm run typecheck -w client
npm run build -w client

# End-to-end API smoke test
powershell -ExecutionPolicy Bypass -File .\scripts\smoke.ps1
```
