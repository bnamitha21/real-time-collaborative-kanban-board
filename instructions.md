# INSTRUCTIONS.md

Standing rules for the Antigravity agent working on **Real-Time Collaborative Kanban Board**.
Read this file fully before every session. Read `PLAN.md` next and continue from the first unchecked step.

---

## 1. What this project is (fixed, do not reinterpret)

A real-time collaborative task board where multiple **organizations**, each with multiple **branches (tenants)**, work with strict data isolation and live synchronization.

Hierarchy: **Organization → Tenants (Branches) → Boards → Columns → Tasks**.

Every board has exactly three predefined columns: **To Do**, **In Progress**, **Completed**.

Roles (exactly three): **Org Admin**, **Tenant Admin**, **Member**.

- Org Admin manages the organization and its branches (create, update, delete).
- Tenant Admin manages boards and tasks inside their branch, creates tasks, assigns them to members.
- Member works on assigned tasks and performs only the actions the role allows.

The specification wording (the assignment PDF and the four requirement documents) is the source of truth. If anything in this file or in `PLAN.md` appears to conflict with it, the specification wins. **Do not rename, drop, or add entities, roles, columns or tables.**

Database tables (exact names): `organizations`, `tenants`, `users`, `memberships`, `boards`, `columns`, `tasks`, `activity_logs`. One helper table, `processed_actions`, is permitted for idempotency (see PLAN Phase 6). No other tables without asking the owner.

## 2. Decisions already made (do not re-debate)

| Concern       | Decision                                                                                                                                                            |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language      | Python for the backend; TypeScript for the frontend with `strict: true`                                                                                             |
| Backend       | Python 3.12+, Flask, `psycopg` (raw SQL, no ORM, so transactions and locking stay explicit)                                                                         |
| Database      | PostgreSQL 16 with Row Level Security as a second isolation layer                                                                                                   |
| Validation    | Pydantic for every request body, query and WebSocket payload                                                                                                        |
| Auth          | Email + password (argon2id), short-lived JWT access token, rotating refresh token in an httpOnly cookie                                                             |
| Real-time     | **WebSockets via Flask-SocketIO** (bidirectional needs: presence, heartbeats, acknowledgements, reconnection). SSE was evaluated and rejected because it is one-way |
| Concurrency   | Optimistic concurrency control with a `version` integer on tasks, enforced inside a DB transaction with `SELECT ... FOR UPDATE`                                     |
| Task ordering | Fractional indexing (`fractional-indexing` package) stored as `position text COLLATE "C"`                                                                           |
| Frontend      | React 18 + Vite + TypeScript, Zustand for state, `@dnd-kit` for drag and drop, plain CSS with design tokens (no UI kit)                                             |
| Scaling       | Socket.IO Redis adapter and Redis presence, enabled when `REDIS_URL` is set; single-node in-memory otherwise                                                        |
| Logging       | Python `logging` with structured JSON output, request-id on every log line                                                                                          |

If a decision truly blocks you, stop and ask the owner. Do not silently swap technology.

## 3. Working method

1. Work **one phase at a time** in `PLAN.md`, in order.
2. Inside a phase: write code, then write the tests listed for that step, then run them.
3. Do not begin the next phase until the phase's **Gate** passes (all listed tests green, lint and typecheck clean).
4. Tick the checkbox in `PLAN.md` only after the step is verified, not before.
5. Commit after every passing step with a conventional message (`feat(server): task move with version check`).
6. Prefer small, reviewable diffs. Never rewrite files that are unrelated to the current step.
7. When a command fails, read the error and fix the cause. Do not disable a test, loosen a type, or add `any` to get green.
8. Never invent endpoints, event names or field names. They are defined in `PLAN.md` and later in `docs/API.md`. If you need a new one, add it to the docs in the same commit.

## 4. Security rules (non-negotiable)

1. **Never trust a tenant id, organization id or role from the client.** Derive scope from the resource in the database, then check the caller's membership.
2. Every query that touches `boards`, `columns`, `tasks` or `activity_logs` runs through `withTenant(tenantId, fn)` so that `app.tenant_id` is set for Row Level Security **and** the SQL also has an explicit `tenant_id = $n` filter. Both layers must exist.
3. If the caller has no access to a resource, respond **404**, not 403, so the existence of other tenants' data is not revealed. Use 403 only when the caller can see the resource but the role forbids the action.
4. WebSocket connections are authenticated at handshake. Rooms are always named with the tenant id (`tenant:{id}` and `tenant:{id}:board:{id}`). A socket may join a room only after the server re-checks membership.
5. Never broadcast a payload to a room that was not derived server-side from the saved record.
6. Passwords are hashed with argon2id. Refresh tokens are stored hashed. Secrets come only from environment variables. `.env` is never committed.
7. Rate-limit auth routes. Set `helmet`, strict CORS (explicit origin list), body size limit 100 kB.
8. Error responses never include stack traces or SQL text. Use the error envelope in section 7.

## 5. Concurrency rules

- A task update or move **must** include `expectedVersion` and `actionId` (UUID). Missing either is a 400.
- The server compares `expectedVersion` with the stored version inside the transaction while holding the row lock. Mismatch → `409 VERSION_CONFLICT` with the current task in the body. Nothing is written.
- A successful write increments `version` by exactly 1, writes an `activity_logs` row, and records the `actionId` in `processed_actions`, all in the same transaction.
- Broadcast only **after** commit.
- Replaying an `actionId` that was already processed returns the original result and does not write again.
- Real-time notifications never replace this check.

## 6. Frontend and design rules

The interface must look like a hand-built product, not a generated template.

**Copy**

- Use the wording from the specification: _Organization_, _Branch_, _To Do_, _In Progress_, _Completed_, _Task Detail_, _Activity_, _Presence_, _Undo_, _Redo_.
- The product title shown in the UI is exactly **Real-Time Collaborative Kanban Board**.
- Sample data uses the specification's examples: _Build Login Page_, _Design Homepage_, _Fix API Bug_.
- No marketing slogans, no "Welcome back!", no "Supercharge your workflow", no emoji, no "Oops!", no lorem ipsum. Messages are plain and specific, for example: "This task was changed by another user. Showing the latest version."

**Visual**

- Use only the tokens in `client/src/styles/tokens.css` (PLAN Phase 8). No hard-coded hex values inside components.
- No gradients, glassmorphism, neon glows, purple-to-blue hero blobs, or decorative illustrations.
- Radius 6px, one soft shadow level, 1px borders in `--line`.
- Fonts: Source Sans 3 (UI) and JetBrains Mono (ids, version numbers), self-hosted through `@fontsource`.
- Spacing on a 4px scale. Type scale 12 / 14 / 16 / 20 / 28.
- Contrast meets WCAG AA. Every interactive element has a visible focus ring.
- Light theme is default; dark theme is supported through the same tokens.

**Behaviour**

- Drag and drop works with mouse, touch and keyboard (space to lift, arrows to move, space to drop).
- Every async action has a loading, success and failure state.
- Connection status is always visible (Connected, Reconnecting, Offline).
- Nothing is labelled "saved" until the server confirms it. Unconfirmed items show a subtle "Pending" marker.

## 7. API conventions

- Base path `/api/v1`. JSON only.
- Success: `{ "data": ... }`. List responses add `{ "meta": { "nextCursor": ... } }`.
- Error envelope: `{ "error": { "code": "VERSION_CONFLICT", "message": "...", "details": ... } }`.
- Codes: `VALIDATION_ERROR` 400, `UNAUTHENTICATED` 401, `FORBIDDEN` 403, `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `RATE_LIMITED` 429, `INTERNAL` 500.
- Timestamps are ISO-8601 UTC. IDs are UUIDv4.
- Lists are paginated (cursor-based) with a default limit of 50 and maximum of 200.

## 8. Code conventions

- Folder layout is fixed (see PLAN Phase 0). Business logic lives in `services/`, never in route handlers. Route handlers: parse, authorize, call service, respond.
- One module per domain: `auth`, `organizations`, `tenants`, `boards`, `columns`, `tasks`, `activity`, `realtime`.
- Functions under 50 lines where practical. No default exports in the server. No circular imports.
- ESLint + Prettier configured in Phase 0 and enforced in the Gate of every phase.
- Comments explain **why**, not what.

## 9. Testing rules

- Write the tests listed in `PLAN.md` for each step. Add more where you see a risk.
- Backend: pytest + Flask test client + Flask-SocketIO test client against a real Postgres test database (never mocks for tenancy or concurrency).
- Frontend: Vitest + Testing Library for stores and components; Playwright for end-to-end with two browser contexts.
- **All test code, test configuration, fixtures, test databases settings, coverage output and reports are excluded from git.** They live only in these locations so one ignore rule set covers them:
  - `server/tests/`
  - `client/tests/`
  - `e2e/`
  - `scripts/test-*.sh`
  - `vitest.config.ts`, `playwright.config.ts`, `.env.test`
  - `coverage/`, `test-results/`, `playwright-report/`
  - any file matching `*.test.ts`, `*.test.tsx`, `*.spec.ts`
- The root `.gitignore` in PLAN Phase 0 contains those rules. Do not place test helpers inside `src/` folders. Production source must not import anything from test locations.
- The `npm run test` scripts are part of `package.json` (committed) so the commands exist for anyone who has the test folders locally.

## 10. Production-ready definition of done

A phase is done only when all are true:

- [ ] Frontend type-checks with `tsc --noEmit` and has zero ESLint errors; backend passes Python syntax checks and linting.
- [ ] All tests for the phase pass locally.
- [ ] No `console.log`, `TODO`, commented-out code, or unused exports remain.
- [ ] Every new endpoint or event is documented in `docs/API.md` or `docs/WEBSOCKET.md`.
- [ ] Migrations are forward-only SQL files and run on an empty database.
- [ ] Environment variables are listed in `.env.example` with a one-line description.
- [ ] Failure paths (bad input, no permission, conflict, network error) have explicit handling and a test.

Final project state must run with `docker compose up --build` using only `.env` values and show a working app at `http://localhost:8080`.

## 11. Things you must not do

- Do not change the spec'd tables, roles, columns, or hierarchy.
- Do not add a UI component library, CSS framework or icon pack with a recognizable template look. Use a small set of inline SVG icons stored in `client/src/components/icons/`.
- Do not store the access token in `localStorage`. Keep it in memory; the refresh cookie restores it.
- Do not use `SELECT *` in production queries that return data to clients; list columns.
- Do not skip a Gate because "it probably works".
- Do not commit generated files, `node_modules`, `dist`, `.env`, or any test code.
