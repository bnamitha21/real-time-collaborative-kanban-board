# PLAN.md — Real-Time Collaborative Kanban Board

Build order for the Antigravity agent. Follow `INSTRUCTIONS.md` throughout.
Each phase has: **Goal → Steps (with scripts) → Tests → Gate**. Tick boxes only after verification.

Phases 0. Repository and tooling

1. Database schema, isolation and seed
2. Backend foundation and authentication
3. Tenancy resolution and RBAC
4. CRUD APIs (organizations, branches, boards, columns, tasks)
5. Task move, ordering and concurrency
6. Activity logs and idempotency
7. WebSocket server: scoped channels and presence
8. Frontend foundation and design system
9. Login, Organization selector, Branch switcher
10. Kanban board and drag and drop
11. Task Detail panel
12. Real-time client, optimistic updates, conflicts
13. Undo and redo
14. Presence and Activity UI
15. Network recovery
16. Edge-case suite
17. Documentation deliverables
18. Production hardening and deployment
19. Final acceptance

---

## Phase 0 — Repository and tooling

**Goal:** an empty but fully wired monorepo with lint, typecheck, test commands and the git ignore rules (including the test-code rules).

### Steps

- [ ] **0.1 Create the repo**

```bash
mkdir kanban-board && cd kanban-board
git init -b main
npm init -y
mkdir -p server/src/{config,db,middleware,modules,realtime,lib} server/migrations server/tests \
         client/src/{api,store,components,pages,styles,lib} client/tests \
         e2e docs scripts
```

- [ ] **0.2 Root `package.json`** (replace generated content)

```json
{
  "name": "real-time-collaborative-kanban-board",
  "private": true,
  "workspaces": ["server", "client"],
  "scripts": {
    "dev:server": "npm run dev -w server",
    "dev:client": "npm run dev -w client",
    "build": "npm run build -w server && npm run build -w client",
    "lint": "eslint . --max-warnings 0",
    "typecheck": "npm run typecheck -w server && npm run typecheck -w client",
    "test": "npm run test -w server && npm run test -w client",
    "test:e2e": "playwright test --config e2e/playwright.config.ts",
    "migrate": "npm run migrate -w server",
    "seed": "npm run seed -w server"
  },
  "devDependencies": {
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "eslint": "^8.57.0",
    "prettier": "^3.2.0",
    "typescript": "^5.4.0",
    "@playwright/test": "^1.44.0"
  },
  "engines": { "node": ">=20" }
}
```

- [ ] **0.3 Root `.gitignore`** (this is where test code is excluded)

```gitignore
# dependencies and builds
node_modules/
dist/
build/
.vite/

# secrets and environment
.env
.env.*
!.env.example

# logs and OS files
*.log
.DS_Store
.idea/
.vscode/

# ---- TEST CODE AND ARTIFACTS (never committed) ----
server/tests/
client/tests/
e2e/
scripts/test-*.sh
vitest.config.ts
**/vitest.config.ts
playwright.config.ts
**/playwright.config.ts
.env.test
coverage/
test-results/
playwright-report/
*.test.ts
*.test.tsx
*.spec.ts
*.spec.tsx
```

- [ ] **0.4 Server workspace**

```bash
cd server
npm init -y
npm i express cors helmet cookie-parser pg zod jsonwebtoken argon2 socket.io \
      pino pino-http express-rate-limit fractional-indexing dotenv uuid
npm i -D typescript tsx @types/node @types/express @types/cors @types/cookie-parser \
         @types/pg @types/jsonwebtoken @types/uuid vitest supertest @types/supertest socket.io-client
cd ..
```

`server/package.json` scripts:

```json
"scripts": {
  "dev": "tsx watch src/index.ts",
  "build": "tsc -p tsconfig.build.json",
  "start": "node dist/index.js",
  "typecheck": "tsc --noEmit",
  "migrate": "tsx src/db/migrate.ts",
  "seed": "tsx src/db/seed.ts",
  "test": "vitest run --config vitest.config.ts"
}
```

`server/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": ".",
    "resolveJsonModule": true
  },
  "include": ["src", "tests", "vitest.config.ts"]
}
```

`server/tsconfig.build.json` (production build excludes tests):

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": { "rootDir": "src" },
  "include": ["src"],
  "exclude": ["tests", "vitest.config.ts"]
}
```

- [ ] **0.5 Client workspace**

```bash
npm create vite@latest client -- --template react-ts
cd client
npm i zustand @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities socket.io-client \
      fractional-indexing idb-keyval @fontsource/source-sans-3 @fontsource/jetbrains-mono
npm i -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
cd ..
```

- [ ] **0.6 Local infrastructure `docker-compose.dev.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: owner
      POSTGRES_PASSWORD: owner_pw
      POSTGRES_DB: kanban
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
  db_test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: owner
      POSTGRES_PASSWORD: owner_pw
      POSTGRES_DB: kanban_test
    ports: ["5433:5432"]
    tmpfs: [/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes: { pgdata: {} }
```

- [ ] **0.7 `.env.example`**

```dotenv
NODE_ENV=development
PORT=4000
CLIENT_ORIGIN=http://localhost:5173
# migrations run as the owner; the app runs as a restricted role so Row Level Security applies
DATABASE_URL_OWNER=postgres://owner:owner_pw@localhost:5432/kanban
DATABASE_URL=postgres://kanban_app:app_pw@localhost:5432/kanban
JWT_ACCESS_SECRET=change-me-at-least-32-characters-long
JWT_ACCESS_TTL_SECONDS=900
REFRESH_TTL_DAYS=14
REDIS_URL=
LOG_LEVEL=info
```

- [ ] **0.8 ESLint + Prettier** (`.eslintrc.cjs`, `.prettierrc`)

```js
// .eslintrc.cjs
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  plugins: ["@typescript-eslint"],
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended"],
  ignorePatterns: ["dist", "node_modules", "client/vite.config.ts"],
  rules: {
    "no-console": "error",
    "@typescript-eslint/no-explicit-any": "error",
  },
};
```

```json
{
  "singleQuote": false,
  "semi": true,
  "printWidth": 100,
  "trailingComma": "all"
}
```

- [ ] **0.9 First commit**

```bash
git add -A && git commit -m "chore: scaffold monorepo"
git status --short | grep -E "tests|e2e|vitest|playwright" && echo "FAIL: test files tracked" || echo "OK: no test files tracked"
```

### Tests

- Create `server/tests/smoke.test.ts`:

```ts
import { describe, it, expect } from "vitest";
describe("toolchain", () => {
  it("runs", () => expect(1 + 1).toBe(2));
});
```

- Create `server/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    globalSetup: ["tests/globalSetup.ts"],
    pool: "forks",
    poolOptions: { forks: { singleFork: true } },
    testTimeout: 15000,
  },
});
```

- Verify ignore rules: `git check-ignore server/tests/smoke.test.ts server/vitest.config.ts` must print both paths.

### Gate

`npm run lint`, `npm run typecheck`, `npm run test` all green; `git ls-files | grep -E "test|spec|e2e"` prints nothing.

---

## Phase 1 — Database schema, isolation and seed

**Goal:** the eight specified tables with tenant scoping, composite foreign keys that make cross-tenant references impossible, efficient ordering, versioning, and Row Level Security.

### Steps

- [ ] **1.1 Migration runner** `server/src/db/migrate.ts`

```ts
import "dotenv/config";
import fs from "node:fs";
import path from "node:path";
import { Client } from "pg";

async function main() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL_OWNER,
  });
  await client.connect();
  await client.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
    name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`);
  const dir = path.resolve(process.cwd(), "migrations");
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".sql"))
    .sort();
  for (const file of files) {
    const done = await client.query(
      "SELECT 1 FROM schema_migrations WHERE name=$1",
      [file],
    );
    if (done.rowCount) continue;
    await client.query("BEGIN");
    try {
      await client.query(fs.readFileSync(path.join(dir, file), "utf8"));
      await client.query("INSERT INTO schema_migrations(name) VALUES ($1)", [
        file,
      ]);
      await client.query("COMMIT");
      process.stdout.write(`applied ${file}\n`);
    } catch (e) {
      await client.query("ROLLBACK");
      throw e;
    }
  }
  await client.end();
}
main().catch((e) => {
  process.stderr.write(`${e}\n`);
  process.exit(1);
});
```

- [ ] **1.2 Migration `server/migrations/001_init.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------- identity ----------
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext NOT NULL UNIQUE,
  name          text   NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  password_hash text   NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  text NOT NULL UNIQUE,
  expires_at  timestamptz NOT NULL,
  revoked_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------- hierarchy ----------
CREATE TABLE organizations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenants (  -- branches
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, name),
  UNIQUE (id, organization_id)
);

CREATE TABLE memberships (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  tenant_id       uuid,
  role            text NOT NULL CHECK (role IN ('org_admin','tenant_admin','member')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, organization_id) REFERENCES tenants(id, organization_id) ON DELETE CASCADE,
  -- org_admin is organization-wide; the other roles belong to exactly one branch
  CHECK ((role = 'org_admin' AND tenant_id IS NULL) OR (role <> 'org_admin' AND tenant_id IS NOT NULL))
);
CREATE UNIQUE INDEX memberships_org_admin_uq ON memberships (user_id, organization_id) WHERE tenant_id IS NULL;
CREATE UNIQUE INDEX memberships_tenant_uq    ON memberships (user_id, tenant_id)       WHERE tenant_id IS NOT NULL;
CREATE INDEX memberships_user_idx ON memberships (user_id);

-- ---------- tenant-scoped business data ----------
CREATE TABLE boards (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  tenant_id       uuid NOT NULL,
  name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, organization_id) REFERENCES tenants(id, organization_id) ON DELETE CASCADE,
  UNIQUE (id, tenant_id)
);
CREATE INDEX boards_tenant_idx ON boards (tenant_id);

CREATE TABLE columns (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL,
  board_id   uuid NOT NULL,
  key        text NOT NULL CHECK (key IN ('todo','in_progress','completed')),
  name       text NOT NULL,
  position   int  NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (board_id, tenant_id) REFERENCES boards(id, tenant_id) ON DELETE CASCADE,
  UNIQUE (board_id, key),
  UNIQUE (id, tenant_id),
  UNIQUE (id, board_id)
);
CREATE INDEX columns_board_idx ON columns (tenant_id, board_id);

CREATE TABLE tasks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL,
  board_id    uuid NOT NULL,
  column_id   uuid NOT NULL,
  title       text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  description text NOT NULL DEFAULT '' CHECK (length(description) <= 10000),
  assignee_id uuid REFERENCES users(id) ON DELETE SET NULL,
  priority    text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
  position    text NOT NULL COLLATE "C",          -- fractional index
  version     integer NOT NULL DEFAULT 1,          -- optimistic concurrency
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (board_id, tenant_id)  REFERENCES boards(id, tenant_id)  ON DELETE CASCADE,
  FOREIGN KEY (column_id, board_id)  REFERENCES columns(id, board_id) ON DELETE CASCADE
);
CREATE INDEX tasks_column_order_idx ON tasks (column_id, position COLLATE "C", id);
CREATE INDEX tasks_tenant_board_idx ON tasks (tenant_id, board_id);
CREATE INDEX tasks_assignee_idx     ON tasks (assignee_id);

CREATE TABLE activity_logs (
  id              bigserial PRIMARY KEY,
  organization_id uuid NOT NULL,
  tenant_id       uuid NOT NULL,
  board_id        uuid,
  task_id         uuid,                      -- no FK: log must outlive a deleted task
  actor_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  action          text NOT NULL CHECK (action IN
                    ('task.created','task.updated','task.moved','task.reordered','task.assigned','task.deleted',
                     'board.created','board.updated','board.deleted')),
  before_value    jsonb,
  after_value     jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, organization_id) REFERENCES tenants(id, organization_id) ON DELETE CASCADE
);
CREATE INDEX activity_tenant_time_idx ON activity_logs (tenant_id, created_at DESC, id DESC);
CREATE INDEX activity_task_idx        ON activity_logs (task_id);

-- idempotency for retried / queued actions (Phase 6)
CREATE TABLE processed_actions (
  action_id  uuid PRIMARY KEY,
  tenant_id  uuid NOT NULL,
  user_id    uuid NOT NULL,
  result     jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX processed_actions_created_idx ON processed_actions (created_at);

-- keep updated_at honest
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END $$ LANGUAGE plpgsql;
CREATE TRIGGER organizations_touch BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER tenants_touch       BEFORE UPDATE ON tenants       FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER boards_touch        BEFORE UPDATE ON boards        FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER tasks_touch         BEFORE UPDATE ON tasks         FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
```

- [ ] **1.3 Migration `002_rls.sql`** — second isolation layer

```sql
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kanban_app') THEN
    CREATE ROLE kanban_app LOGIN PASSWORD 'app_pw';
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO kanban_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kanban_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kanban_app;
REVOKE ALL ON schema_migrations FROM kanban_app;

ALTER TABLE boards            ENABLE ROW LEVEL SECURITY;
ALTER TABLE columns           ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks             ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_actions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON boards            USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation ON columns           USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation ON tasks             USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation ON activity_logs     USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation ON processed_actions USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
```

The `kanban_app` role does not own the tables, so RLS applies to it. With no tenant set, `nullif(...)::uuid` is `NULL`, so no rows match: queries fail closed.

- [ ] **1.4 DB helper** `server/src/db/pool.ts`

```ts
import { Pool, PoolClient } from "pg";
import { env } from "../config/env.js";

export const pool = new Pool({ connectionString: env.DATABASE_URL, max: 20 });

export async function withTx<T>(fn: (c: PoolClient) => Promise<T>): Promise<T> {
  const c = await pool.connect();
  try {
    await c.query("BEGIN");
    const r = await fn(c);
    await c.query("COMMIT");
    return r;
  } catch (e) {
    await c.query("ROLLBACK");
    throw e;
  } finally {
    c.release();
  }
}

/** Every tenant-scoped query must go through this so Row Level Security has a tenant. */
export function withTenant<T>(
  tenantId: string,
  fn: (c: PoolClient) => Promise<T>,
): Promise<T> {
  return withTx(async (c) => {
    await c.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);
    return fn(c);
  });
}
```

- [ ] **1.5 Seed** `server/src/db/seed.ts` (uses the owner connection; development only; refuses to run when `NODE_ENV=production`)

Create:

- Organization **Northwind Traders** with branches **Hyderabad** and **Vijayawada**; Organization **Contoso Retail** with branch **Chennai**.
- Users (password for all: `Passw0rd!` in development only):
  - `orgadmin@northwind.test` → org_admin of Northwind
  - `admin.hyd@northwind.test` → tenant_admin of Hyderabad
  - `member.hyd@northwind.test`, `member2.hyd@northwind.test` → member of Hyderabad
  - `admin.vja@northwind.test` → tenant_admin of Vijayawada
  - `admin@contoso.test` → org_admin of Contoso
  - `multi@northwind.test` → member of **both** Hyderabad and Vijayawada (exercises the branch switcher)
- One board per branch, called **Sprint Board**, with the three columns (`To Do`, `In Progress`, `Completed`).
- Tasks in Hyderabad: **Build Login Page**, **Design Homepage**, **Fix API Bug** in To Do, positions generated with `generateKeyBetween`.

Because the spec uses these exact examples, keep them verbatim.

### Tests (`server/tests/db/`)

- `globalSetup.ts` (runs once): connects as owner to `kanban_test`, drops and recreates schema `public`, runs migrations, exports `DATABASE_URL`/`DATABASE_URL_OWNER` for the test process.
- `schema.test.ts`
  - all eight spec tables exist
  - inserting a task whose `column_id` belongs to another board → fails (FK `(column_id, board_id)`)
  - inserting a task with `tenant_id` of branch B but `board_id` of branch A → fails (FK `(board_id, tenant_id)`)
  - inserting a membership with `role='org_admin'` and a tenant → fails (CHECK)
  - two `org_admin` rows for the same user and organization → fails (partial unique)
  - a tenant of org A cannot be referenced by a membership of org B → fails (composite FK)
- `rls.test.ts`
  - connect as `kanban_app`, no `app.tenant_id` → `SELECT count(*) FROM tasks` returns 0
  - set tenant A → sees only tenant A tasks
  - set tenant A, `INSERT` task with tenant B id → fails RLS `WITH CHECK`
  - set tenant A, `UPDATE tasks SET title='x' WHERE tenant_id = B` → 0 rows
- `ordering.test.ts`: insert 1,000 tasks with spaced fractional keys, `EXPLAIN` the column-order query and assert it uses `tasks_column_order_idx`.

### Gate

Migrations apply on an empty DB; `npm run test -w server` green for all db tests.

---

## Phase 2 — Backend foundation and authentication

**Goal:** a typed Express app with config validation, logging, error envelope, and auth.

### Steps

- [ ] **2.1 Env validation** `server/src/config/env.ts`

```ts
import "dotenv/config";
import { z } from "zod";

const schema = z.object({
  NODE_ENV: z
    .enum(["development", "test", "production"])
    .default("development"),
  PORT: z.coerce.number().default(4000),
  CLIENT_ORIGIN: z.string().url(),
  DATABASE_URL: z.string().min(1),
  DATABASE_URL_OWNER: z.string().optional(),
  JWT_ACCESS_SECRET: z.string().min(32),
  JWT_ACCESS_TTL_SECONDS: z.coerce.number().default(900),
  REFRESH_TTL_DAYS: z.coerce.number().default(14),
  REDIS_URL: z
    .string()
    .optional()
    .transform((v) => v || undefined),
  LOG_LEVEL: z.string().default("info"),
});
export const env = schema.parse(process.env);
```

- [ ] **2.2 Errors** `server/src/lib/errors.ts`

```ts
export class AppError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}
export const badRequest = (m: string, d?: unknown) =>
  new AppError(400, "VALIDATION_ERROR", m, d);
export const unauthenticated = (m = "Authentication required") =>
  new AppError(401, "UNAUTHENTICATED", m);
export const forbidden = (m = "You do not have permission to do this") =>
  new AppError(403, "FORBIDDEN", m);
export const notFound = (m = "Not found") => new AppError(404, "NOT_FOUND", m);
export class VersionConflict extends AppError {
  constructor(public current: unknown) {
    super(409, "VERSION_CONFLICT", "This task was changed by another user.", {
      current,
    });
  }
}
```

`server/src/middleware/error.ts` maps `AppError` → envelope, `ZodError` → 400 with field details, anything else → 500 `INTERNAL` (logged with request id, message hidden from client).

- [ ] **2.3 App factory** `server/src/app.ts` — `helmet()`, `cors({ origin: env.CLIENT_ORIGIN, credentials: true })`, `express.json({ limit: "100kb" })`, `cookieParser()`, `pino-http` with `genReqId`, `GET /healthz` (process up) and `GET /readyz` (does `SELECT 1`), router mounted at `/api/v1`, 404 handler, error handler. Export `createApp()` (used by tests) separately from `index.ts` (which listens and attaches Socket.IO).

- [ ] **2.3b Zod validate helper** `server/src/middleware/validate.ts`

```ts
import { ZodSchema } from "zod";
import { RequestHandler } from "express";
export const validate =
  (s: {
    body?: ZodSchema;
    query?: ZodSchema;
    params?: ZodSchema;
  }): RequestHandler =>
  (req, _res, next) => {
    try {
      if (s.body) req.body = s.body.parse(req.body);
      if (s.query) req.query = s.query.parse(req.query) as never;
      if (s.params) req.params = s.params.parse(req.params) as never;
      next();
    } catch (e) {
      next(e);
    }
  };
```

- [ ] **2.4 Auth module** `server/src/modules/auth/`
  - `POST /auth/register` `{ email, name, password }` (min 10 chars). Creates a user only; access comes from memberships added by admins. Rate limited 10/min/IP.
  - `POST /auth/login` → `{ data: { accessToken, user } }` and sets `refresh` cookie (`httpOnly; secure in prod; sameSite=lax; path=/api/v1/auth`). Same error message for unknown email and wrong password. Rate limited.
  - `POST /auth/refresh` → rotates the refresh token (old one revoked), returns a new access token. Reuse of a revoked token revokes all of that user's tokens.
  - `POST /auth/logout` revokes the token and clears the cookie.
  - `GET /auth/me` → user + `workspaces` (see Phase 3).
  - Access token claims: `sub`, `iat`, `exp`. **No roles or tenant ids in the token**; permissions are always read from `memberships`, so revocation is immediate.

```ts
// server/src/modules/auth/password.ts
import argon2 from "argon2";
export const hashPassword = (p: string) =>
  argon2.hash(p, { type: argon2.argon2id });
export const verifyPassword = (hash: string, p: string) =>
  argon2.verify(hash, p);
```

```ts
// server/src/middleware/authenticate.ts
import jwt from "jsonwebtoken";
export const authenticate: RequestHandler = (req, _res, next) => {
  const h = req.headers.authorization;
  if (!h?.startsWith("Bearer ")) return next(unauthenticated());
  try {
    const p = jwt.verify(h.slice(7), env.JWT_ACCESS_SECRET) as { sub: string };
    req.user = { id: p.sub };
    next();
  } catch {
    next(unauthenticated("Session expired"));
  }
};
```

### Tests (`server/tests/auth/`)

- register: valid → 201; duplicate email (different case) → 409-style `VALIDATION_ERROR`; short password → 400.
- login: correct → token + cookie flags (`HttpOnly`); wrong password and unknown email return identical body.
- `GET /auth/me` without token → 401; with expired token → 401; with tampered token → 401.
- refresh: rotation works once; reusing the old token → 401 and all tokens revoked.
- rate limit: 11th login within a minute → 429.
- password hash in DB starts with `$argon2id$`; no endpoint ever returns `password_hash`.
- `/healthz` 200, `/readyz` 200; stop DB pool → `/readyz` 503.

### Gate

All auth tests green. `curl -i localhost:4000/healthz` returns 200.

---

## Phase 3 — Tenancy resolution and RBAC

**Goal:** one place that answers "may this user do X on this resource?", used by every route and by the WebSocket server.

### Steps

- [ ] **3.1 Access resolver** `server/src/modules/access/access.ts`

```ts
export type Role = "org_admin" | "tenant_admin" | "member";
export interface TenantAccess {
  organizationId: string;
  tenantId: string;
  role: Role;
}

/** Highest-privilege access the user holds for this tenant, or null. Never throws for "no access". */
export async function resolveTenantAccess(
  userId: string,
  tenantId: string,
): Promise<TenantAccess | null> {
  const { rows } = await pool.query(
    `SELECT t.organization_id AS "organizationId", t.id AS "tenantId", m.role
       FROM tenants t
       JOIN memberships m
         ON m.user_id = $1
        AND m.organization_id = t.organization_id
        AND (m.tenant_id = t.id OR m.role = 'org_admin')
      WHERE t.id = $2
      ORDER BY (m.role = 'org_admin') DESC, (m.role = 'tenant_admin') DESC
      LIMIT 1`,
    [userId, tenantId],
  );
  return rows[0] ?? null;
}

export async function resolveOrgRole(
  userId: string,
  orgId: string,
): Promise<"org_admin" | "member_of_org" | null> {
  /* org_admin row → 'org_admin'; any membership in org → 'member_of_org'; else null */
}
```

`pool` here is the plain pool: `tenants`, `memberships`, `organizations` are not under RLS, so lookup works without `app.tenant_id`.

- [ ] **3.2 Permission table** `server/src/modules/access/permissions.ts` — single source of truth

```ts
export const PERMISSIONS = {
  "org.read": ["org_admin", "tenant_admin", "member"],
  "org.update": ["org_admin"],
  "org.delete": ["org_admin"],
  "tenant.create": ["org_admin"],
  "tenant.read": ["org_admin", "tenant_admin", "member"],
  "tenant.update": ["org_admin"],
  "tenant.delete": ["org_admin"],
  "board.read": ["org_admin", "tenant_admin", "member"],
  "board.create": ["org_admin", "tenant_admin"],
  "board.update": ["org_admin", "tenant_admin"],
  "board.delete": ["org_admin", "tenant_admin"],
  "column.read": ["org_admin", "tenant_admin", "member"],
  "column.update": ["org_admin", "tenant_admin"],
  "task.read": ["org_admin", "tenant_admin", "member"],
  "task.create": ["org_admin", "tenant_admin"],
  "task.assign": ["org_admin", "tenant_admin"],
  "task.delete": ["org_admin", "tenant_admin"],
  "task.update": ["org_admin", "tenant_admin", "member:own"], // member only when assigned to them
  "task.move": ["org_admin", "tenant_admin", "member:own"],
  "activity.read": ["org_admin", "tenant_admin", "member"],
} as const;
export type Permission = keyof typeof PERMISSIONS;

export function can(
  role: Role,
  perm: Permission,
  ctx?: { isAssignee?: boolean },
): boolean {
  const allowed = PERMISSIONS[perm] as readonly string[];
  if (allowed.includes(role)) return true;
  return (
    role === "member" &&
    allowed.includes("member:own") &&
    ctx?.isAssignee === true
  );
}
```

- [ ] **3.3 Express guards** `server/src/middleware/tenantAccess.ts`
  - `loadBoardScope(boardId)` → `SELECT tenant_id, organization_id FROM boards WHERE id=$1` using the **owner-free** lookup (a `SECURITY DEFINER` SQL function `board_scope(uuid)` created in migration `003_scope_fns.sql`, returns only `tenant_id, organization_id`). This avoids needing a tenant to find the tenant, and leaks nothing because the caller still must pass `resolveTenantAccess`.
  - Same function `task_scope(uuid)` → `tenant_id, board_id`.
  - `requireTenantAccess(perm)` — takes the tenant id from the **resource**, calls `resolveTenantAccess`, returns 404 if null, 403 if `!can(...)`, and attaches `req.access`.

```sql
-- 003_scope_fns.sql
CREATE OR REPLACE FUNCTION board_scope(p_id uuid)
RETURNS TABLE (tenant_id uuid, organization_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$ SELECT b.tenant_id, b.organization_id FROM boards b WHERE b.id = p_id $$;

CREATE OR REPLACE FUNCTION task_scope(p_id uuid)
RETURNS TABLE (tenant_id uuid, board_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$ SELECT t.tenant_id, t.board_id FROM tasks t WHERE t.id = p_id $$;

REVOKE ALL ON FUNCTION board_scope(uuid), task_scope(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION board_scope(uuid), task_scope(uuid) TO kanban_app;
```

- [ ] **3.4 Workspaces endpoint** `GET /me/workspaces` → feeds the Organization selector and Branch switcher:

```json
{
  "data": [
    {
      "organization": { "id": "…", "name": "Northwind Traders" },
      "role": "member",
      "tenants": [
        { "id": "…", "name": "Hyderabad", "role": "member" },
        { "id": "…", "name": "Vijayawada", "role": "member" }
      ]
    }
  ]
}
```

For an Org Admin, `tenants` lists **all** branches of the organization. For others, only the branches in their memberships.

### Tests (`server/tests/rbac/`)

Build a fixture helper that seeds two organizations, three branches and one user per role, and returns tokens.

- Table-driven test: for every `(role, permission)` pair assert `can()` equals the matrix in section 3.2.
- `resolveTenantAccess`: org admin of Northwind → access to Hyderabad and Vijayawada, none to Chennai; tenant admin of Hyderabad → none to Vijayawada; `multi@…` → both with role `member`.
- `/me/workspaces` returns exactly the expected branches for each fixture user.
- Member who is not the assignee: `can(member,'task.move',{isAssignee:false}) === false`; assignee → true.
- Guard returns **404** (not 403) for a board in a tenant the caller has no relation to; **403** when caller is a member trying `board.create` in their own tenant.

### Gate

RBAC suite green; coverage of `access/` above 95 percent (check locally, not committed).

---

## Phase 4 — CRUD APIs

**Goal:** the full CRUD surface for Organizations, Tenants (Branches), Boards, Columns, Tasks with correct relationships and isolation.

### Routes

| Method           | Path                                 | Permission                                       | Notes                                                                    |
| ---------------- | ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------------------ |
| POST             | `/organizations`                     | any authenticated user                           | caller becomes `org_admin` (single transaction creates org + membership) |
| GET              | `/organizations`                     | —                                                | only organizations where caller has a membership                         |
| GET              | `/organizations/:orgId`              | `org.read`                                       |                                                                          |
| PATCH            | `/organizations/:orgId`              | `org.update`                                     |                                                                          |
| DELETE           | `/organizations/:orgId`              | `org.delete`                                     | cascades                                                                 |
| POST             | `/organizations/:orgId/tenants`      | `tenant.create`                                  |                                                                          |
| GET              | `/organizations/:orgId/tenants`      | filtered to caller's branches unless org admin   |                                                                          |
| GET/PATCH/DELETE | `/tenants/:tenantId`                 | `tenant.read/update/delete`                      |                                                                          |
| POST             | `/tenants/:tenantId/members`         | org admin (any role), tenant admin (member only) | add user by email to a branch                                            |
| DELETE           | `/tenants/:tenantId/members/:userId` | same                                             | also forces that user's sockets to leave (Phase 7)                       |
| POST             | `/tenants/:tenantId/boards`          | `board.create`                                   | creates board **and** its three columns in one transaction               |
| GET              | `/tenants/:tenantId/boards`          | `board.read`                                     | paginated                                                                |
| GET              | `/boards/:boardId`                   | `board.read`                                     | returns board + columns + tasks ordered by `position` (the "snapshot")   |
| PATCH/DELETE     | `/boards/:boardId`                   | `board.update/delete`                            |                                                                          |
| GET              | `/boards/:boardId/columns`           | `column.read`                                    |                                                                          |
| PATCH            | `/columns/:columnId`                 | `column.update`                                  | rename only                                                              |
| POST             | `/boards/:boardId/tasks`             | `task.create`                                    | `{ columnId, title, description?, assigneeId?, priority?, actionId }`    |
| GET              | `/tasks/:taskId`                     | `task.read`                                      |                                                                          |
| PATCH            | `/tasks/:taskId`                     | `task.update` / `task.assign`                    | requires `expectedVersion`, `actionId`                                   |
| DELETE           | `/tasks/:taskId`                     | `task.delete`                                    | requires `expectedVersion` (query) and `actionId`                        |
| POST             | `/tasks/:taskId/move`                | `task.move`                                      | Phase 5                                                                  |
| GET              | `/tenants/:tenantId/activity`        | `activity.read`                                  | Phase 6                                                                  |

Columns: the three columns are predefined and created with the board; they cannot be created or deleted by themselves (deleting the board deletes them). `PATCH` allows renaming the display name only; `key` and `position` are immutable. This keeps the spec rule "each board contains three predefined columns".

### Steps

- [ ] **4.1** Zod schemas per module in `modules/<name>/schemas.ts`. Reject unknown keys with `.strict()`.
- [ ] **4.2** Services in `modules/<name>/service.ts`. All tenant-scoped SQL runs inside `withTenant()`.
- [ ] **4.3** Board creation transaction:

```ts
export async function createBoard(ctx: Ctx, tenantId: string, name: string) {
  return withTenant(tenantId, async (c) => {
    const {
      rows: [board],
    } = await c.query(
      `INSERT INTO boards (organization_id, tenant_id, name, created_by)
       VALUES ($1,$2,$3,$4) RETURNING id, name, tenant_id AS "tenantId", organization_id AS "organizationId"`,
      [ctx.organizationId, tenantId, name, ctx.userId],
    );
    const cols = [
      ["todo", "To Do"],
      ["in_progress", "In Progress"],
      ["completed", "Completed"],
    ];
    for (let i = 0; i < cols.length; i++) {
      await c.query(
        `INSERT INTO columns (tenant_id, board_id, key, name, position) VALUES ($1,$2,$3,$4,$5)`,
        [tenantId, board.id, cols[i]![0], cols[i]![1], i],
      );
    }
    await logActivity(c, {
      ...ctx,
      tenantId,
      boardId: board.id,
      action: "board.created",
      after: { name },
    });
    return board;
  });
}
```

- [ ] **4.4** Task create assigns position at the **bottom** of the column: `generateKeyBetween(lastPositionInColumn, null)`. Assignee must be a member (or admin) of the same tenant; otherwise 422-style `VALIDATION_ERROR` "Assignee does not belong to this branch".
- [ ] **4.5** Task update changes only provided fields, always `WHERE id=$1 AND tenant_id=$2 AND version=$3`, with `SET version = version + 1`. See Phase 5 for the locked version.
- [ ] **4.6** Snapshot query for `GET /boards/:boardId`:

```sql
SELECT id, column_id AS "columnId", title, description, assignee_id AS "assigneeId",
       priority, position, version, updated_at AS "updatedAt"
  FROM tasks
 WHERE tenant_id = $1 AND board_id = $2
 ORDER BY column_id, position COLLATE "C", id;
```

### Tests (`server/tests/crud/`)

- Organization: create → creator is org_admin; list shows only own organizations; update/delete by tenant admin → 403; by outsider → 404.
- Tenants: org admin creates; duplicate branch name in the same organization → `VALIDATION_ERROR`; same name in different organization allowed.
- Boards: creating a board produces exactly three columns named `To Do`, `In Progress`, `Completed` in that order; member cannot create (403); tenant admin of another branch gets 404.
- Columns: rename works; attempts to change `key` or `position` → 400 (strict schema); no POST/DELETE route exists (404).
- Tasks: create lands at bottom; create in a column of another board → 400; assignee from another tenant → 400; GET after create returns ordered list; delete by member → 403.
- Pagination: 120 boards → page 1 has 50 with `nextCursor`; following cursor yields next 50, no duplicates.
- Validation: unknown body keys rejected; title of 201 chars rejected; invalid UUID path param → 400.

### Gate

CRUD suite green; manual run of the seed + a short `curl` script (`scripts/smoke.sh`, committed, no test code inside) that logs in and lists a board works.

---

## Phase 5 — Task move, ordering and concurrency

**Goal:** correct, race-free moves and reorders using optimistic concurrency control, with server-computed fractional positions.

### Contract

`POST /tasks/:taskId/move`

```json
{
  "expectedVersion": 3,
  "toColumnId": "…",
  "afterTaskId": "…or null",
  "actionId": "uuid"
}
```

`afterTaskId` is the task that should sit directly above the moved task in the destination column (`null` = top of the column). The server computes the actual fractional position from the **current** neighbours, so the client never invents positions.

Success → `200 { data: { task } }` with the incremented `version`.
Stale → `409 VERSION_CONFLICT` with `error.details.current` containing the latest task.

### Steps

- [ ] **5.1 Service** `server/src/modules/tasks/move.ts`

```ts
import { generateKeyBetween } from "fractional-indexing";

export async function moveTask(ctx: Ctx, taskId: string, input: MoveInput) {
  return withTenant(ctx.tenantId, async (c) => {
    // 1. idempotency: a retried action returns the first result
    const seen = await c.query(
      "SELECT result FROM processed_actions WHERE action_id = $1",
      [input.actionId],
    );
    if (seen.rowCount)
      return {
        task: seen.rows[0].result as TaskDto,
        replayed: true,
        event: null,
      };

    // 2. take the row lock; concurrent movers queue here
    const {
      rows: [task],
    } = await c.query(
      `SELECT id, board_id, column_id, assignee_id, position, version, title
         FROM tasks WHERE id = $1 AND tenant_id = $2 FOR UPDATE`,
      [taskId, ctx.tenantId],
    );
    if (!task) throw notFound("Task not found");

    // 3. permission (member only for own tasks)
    if (
      !can(ctx.role, "task.move", {
        isAssignee: task.assignee_id === ctx.userId,
      })
    )
      throw forbidden();

    // 4. optimistic concurrency check
    if (task.version !== input.expectedVersion) {
      throw new VersionConflict(await fetchTaskDto(c, ctx.tenantId, taskId));
    }

    // 5. destination column must belong to the same board
    const col = await c.query(
      "SELECT id, key FROM columns WHERE id=$1 AND board_id=$2 AND tenant_id=$3",
      [input.toColumnId, task.board_id, ctx.tenantId],
    );
    if (!col.rowCount)
      throw badRequest("Destination column is not on this board");

    // 6. neighbours computed server-side from current data
    let prev: string | null = null;
    if (input.afterTaskId) {
      const a = await c.query(
        "SELECT position FROM tasks WHERE id=$1 AND column_id=$2 AND tenant_id=$3 AND id <> $4",
        [input.afterTaskId, input.toColumnId, ctx.tenantId, taskId],
      );
      if (!a.rowCount)
        throw badRequest("afterTaskId is not in the destination column");
      prev = a.rows[0].position;
    }
    const nextRow = await c.query(
      `SELECT position FROM tasks
        WHERE column_id=$1 AND tenant_id=$2 AND id <> $3
          AND ($4::text IS NULL OR position COLLATE "C" > $4::text COLLATE "C")
        ORDER BY position COLLATE "C" ASC, id ASC LIMIT 1`,
      [input.toColumnId, ctx.tenantId, taskId, prev],
    );
    const next: string | null = nextRow.rows[0]?.position ?? null;
    const position = generateKeyBetween(prev, next);

    // 7. write + version bump
    const {
      rows: [updated],
    } = await c.query(
      `UPDATE tasks SET column_id=$1, position=$2, version = version + 1
        WHERE id=$3 AND tenant_id=$4 AND version=$5
        RETURNING id, board_id AS "boardId", column_id AS "columnId", title, description,
                  assignee_id AS "assigneeId", priority, position, version, updated_at AS "updatedAt"`,
      [input.toColumnId, position, taskId, ctx.tenantId, input.expectedVersion],
    );

    // 8. audit + idempotency record, same transaction
    const sameColumn = task.column_id === input.toColumnId;
    await logActivity(c, {
      ...ctx,
      boardId: task.board_id,
      taskId,
      action: sameColumn ? "task.reordered" : "task.moved",
      before: {
        columnId: task.column_id,
        position: task.position,
        version: task.version,
      },
      after: { columnId: input.toColumnId, position, version: updated.version },
    });
    await c.query(
      "INSERT INTO processed_actions (action_id, tenant_id, user_id, result) VALUES ($1,$2,$3,$4)",
      [input.actionId, ctx.tenantId, ctx.userId, JSON.stringify(updated)],
    );

    return {
      task: updated,
      replayed: false,
      event: sameColumn ? "task:reordered" : "task:moved",
    };
  });
}
```

The route handler broadcasts **after** `withTenant` resolves (commit complete) and only if `replayed === false`.

- [ ] **5.2** Apply the same pattern (lock → permission → version check → write → log → idempotency) to `PATCH /tasks/:id` and `DELETE /tasks/:id`. `task.assign` is checked separately when `assigneeId` is in the body.
- [ ] **5.3 Rebalancing safeguard**: fractional keys grow when users repeatedly insert at the same spot. Add a nightly-safe maintenance function `rebalanceColumn(tenantId, columnId)` that rewrites keys with `generateNKeysBetween(null, null, n)` inside one transaction while locking the column's tasks `FOR UPDATE` and bumping each task's version. Trigger it from the move service when `position.length > 64`. Broadcast `board:resync` afterwards so clients refetch.
- [ ] **5.4 Deadlock avoidance**: always lock rows in a deterministic order (task id ascending) when an operation touches more than one task (rebalance only).

### Tests (`server/tests/concurrency/`)

- **Spec scenario**: task _Fix API Bug_ at version 1. Fire two moves with `Promise.all` and the same `expectedVersion=1`: one to In Progress, one to Completed. Assert exactly one `200` and one `409`; final column equals the winner's target; final `version === 2`; the 409 body contains the winner's state.
- 50 parallel moves of the same task from the same version → exactly 1 success, 49 conflicts, version 2.
- 20 different tasks moved in parallel into the same column at the same `afterTaskId` → all succeed, all positions distinct, ordering is deterministic and stable across 10 repeated reads.
- Description edit vs status move at the same version: one wins, the other gets 409 (version check applies to every field) and the loser's retry with the new version succeeds and preserves the winner's change.
- Idempotency: same `actionId` sent twice → second call returns the same body, version incremented once, one activity row.
- Move with `toColumnId` from another board → 400; from another tenant → 400; token from other tenant → 404.
- Member moving a task not assigned to them → 403; assigned to them → 200.
- Reorder inside the same column: sequence of 100 random reorders keeps `ORDER BY position` equal to an in-memory model of the list.
- Fractional key growth: 200 insertions at the top of a column triggers rebalance; afterwards order is unchanged and all versions incremented.
- Rolled-back transaction emits nothing: inject a failure after the UPDATE (spy on `logActivity` to throw) and assert the task is unchanged and no event was published.

### Gate

Concurrency suite green and stable across 20 consecutive runs (`for i in $(seq 20); do npm run test -w server -- tests/concurrency || break; done`).

---

## Phase 6 — Activity logs and idempotency

**Goal:** every important action is recorded in the same transaction as the change, readable only within authorized tenants.

### Steps

- [ ] **6.1 `logActivity`** `server/src/modules/activity/log.ts`

```ts
export async function logActivity(
  c: PoolClient,
  e: {
    organizationId: string;
    tenantId: string;
    boardId?: string;
    taskId?: string;
    userId: string;
    action: ActivityAction;
    before?: unknown;
    after?: unknown;
  },
) {
  await c.query(
    `INSERT INTO activity_logs (organization_id, tenant_id, board_id, task_id, actor_id, action, before_value, after_value)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
    [
      e.organizationId,
      e.tenantId,
      e.boardId ?? null,
      e.taskId ?? null,
      e.userId,
      e.action,
      e.before ? JSON.stringify(e.before) : null,
      e.after ? JSON.stringify(e.after) : null,
    ],
  );
}
```

- [ ] **6.2** Call it from create, update (`task.updated`, plus `task.assigned` when assignee changes), delete, move, reorder, and board create/update/delete.
- [ ] **6.3** `GET /tenants/:tenantId/activity?boardId&taskId&cursor&limit` returns entries newest first with actor name, task title at time of action (stored inside `after_value`/`before_value` as `title`), and a human sentence built on the client from structured data.
- [ ] **6.4** Cleanup job for `processed_actions` older than 7 days (`setInterval` in `index.ts`, once per hour, run as `DELETE ... WHERE created_at < now() - interval '7 days'` inside a short transaction with an advisory lock so only one instance runs it).

### Tests (`server/tests/activity/`)

- Every mutating endpoint writes exactly one activity row with the correct `action`, `actor_id`, `tenant_id`, `organization_id`.
- Moving _Fix API Bug_ To Do → In Progress logs `before.columnId` and `after.columnId` correctly.
- Rejected (409/403) operations write **no** activity row.
- Activity is readable by members of the tenant, 404 for outsiders; org admin sees all branches but each call is scoped to one tenant id.
- Deleting a task keeps its log rows.
- Cursor pagination: no duplicates or gaps with 150 entries created in the same millisecond (`ORDER BY created_at DESC, id DESC` with `(created_at,id)` cursor).

### Gate

Activity suite green.

---

## Phase 7 — WebSocket server: scoped channels and presence

**Goal:** authenticated, tenant-scoped real-time channels, presence with heartbeats, and the same isolation guarantees as the REST API.

### Room model

- `tenant:{tenantId}` — presence updates for that branch only.
- `tenant:{tenantId}:board:{boardId}` — task and board events.
- `user:{userId}` — private notices (for example "access revoked").

### Event contract (also write to `docs/WEBSOCKET.md`)

Client → server (all with acknowledgement callback):
| Event | Payload | Ack |
|---|---|---|
| `board:subscribe` | `{ boardId }` | `{ ok: true, presence: PresenceUser[] }` or `{ ok:false, code:'NOT_FOUND' }` |
| `board:unsubscribe` | `{ boardId }` | `{ ok: true }` |

Server → client:
| Event | Payload |
|---|---|
| `task:created` | `{ task, actorId, actionId }` |
| `task:updated` | `{ task, actorId, actionId }` |
| `task:moved` | `{ task, fromColumnId, actorId, actionId }` |
| `task:reordered` | `{ task, actorId, actionId }` |
| `task:deleted` | `{ taskId, version, actorId, actionId }` |
| `board:updated` / `board:deleted` | `{ board }` / `{ boardId }` |
| `board:resync` | `{ boardId }` |
| `presence:update` | `{ tenantId, users: [{ userId, name, online }] }` |
| `access:revoked` | `{ tenantId }` |

Writes still go through REST (so there is one validated, audited path); sockets deliver the accepted result.

### Steps

- [ ] **7.1 Attach Socket.IO** `server/src/realtime/index.ts`

```ts
import { Server } from "socket.io";
import jwt from "jsonwebtoken";

export function attachRealtime(httpServer: import("http").Server) {
  const io = new Server(httpServer, {
    cors: { origin: env.CLIENT_ORIGIN, credentials: true },
    pingInterval: 10_000, // heartbeat
    pingTimeout: 8_000, // dead connection detected within ~18 s
    maxHttpBufferSize: 1e5,
  });

  io.use((socket, next) => {
    try {
      const p = jwt.verify(
        String(socket.handshake.auth?.token ?? ""),
        env.JWT_ACCESS_SECRET,
      ) as { sub: string; exp: number };
      socket.data.userId = p.sub;
      socket.data.exp = p.exp;
      next();
    } catch {
      next(new Error("UNAUTHENTICATED"));
    }
  });

  io.on("connection", (socket) => {
    socket.join(`user:${socket.data.userId}`);
    const expiryTimer = setTimeout(
      () => socket.disconnect(true),
      Math.max(0, socket.data.exp * 1000 - Date.now()),
    );
    socket.on("disconnect", () => {
      clearTimeout(expiryTimer);
      presence.leaveAll(socket);
    });

    socket.on("board:subscribe", async (raw, ack) => {
      const parsed = z.object({ boardId: z.string().uuid() }).safeParse(raw);
      if (!parsed.success)
        return ack?.({ ok: false, code: "VALIDATION_ERROR" });
      const scope = await boardScope(parsed.data.boardId); // SECURITY DEFINER lookup
      const access =
        scope &&
        (await resolveTenantAccess(socket.data.userId, scope.tenant_id));
      if (!scope || !access) return ack?.({ ok: false, code: "NOT_FOUND" }); // same answer for "missing" and "forbidden"
      await leaveOtherBoards(socket);
      await socket.join(`tenant:${scope.tenant_id}`);
      await socket.join(
        `tenant:${scope.tenant_id}:board:${parsed.data.boardId}`,
      );
      const users = await presence.join(io, socket, scope.tenant_id);
      ack?.({ ok: true, presence: users });
    });
    socket.on("board:unsubscribe" /* leave board room only */);
  });
  return io;
}
```

- [ ] **7.2 Publisher** `server/src/realtime/publisher.ts`: `publishToBoard(tenantId, boardId, event, payload)` emits to `tenant:{tenantId}:board:{boardId}`. The function signature requires both ids so a caller cannot broadcast without a tenant. Called only from route handlers after commit.
- [ ] **7.3 Presence** `server/src/realtime/presence.ts`
  - In-memory: `Map<tenantId, Map<userId, Set<socketId>>>`. A user is online while the set is non-empty, so multiple tabs work and one closed tab does not mark them offline.
  - On join/leave, emit `presence:update` to `tenant:{tenantId}` with the full online list. Offline users appear as `online:false` using the tenant's member list from the database.
  - Network loss: Socket.IO ping timeout fires `disconnect`, presence updates within ~18 seconds.
  - Scale-out: when `REDIS_URL` is set, use `@socket.io/redis-adapter` (`npm i @socket.io/redis-adapter redis -w server`) and store presence as a Redis hash per tenant with per-socket keys that expire (TTL 30 s, refreshed on every ping). Interface stays the same.
- [ ] **7.4 Revocation**: when a membership is removed or changed, emit `access:revoked` to `user:{id}` and call `io.in("user:{id}").fetchSockets()` then re-run `resolveTenantAccess`; sockets that lost access leave the tenant rooms and receive `access:revoked`.
- [ ] **7.5** Hook `publishToBoard` calls into create, update, move, reorder, delete handlers. Payload is built from the committed row, never from request input.

### Tests (`server/tests/realtime/`) using `socket.io-client` against a real listening server

- Connect without token → connection error `UNAUTHENTICATED`; expired token → error; valid → connected.
- User of Hyderabad subscribes to a Hyderabad board → `ok:true`. Same user subscribes to a Vijayawada board id → `ok:false NOT_FOUND`; to a Chennai (other organization) board → identical `NOT_FOUND`.
- Broadcast isolation: sockets A (Hyderabad), B (Hyderabad), C (Vijayawada), D (Contoso). A moves a task through REST. B receives `task:moved`; C and D receive **nothing** within 1 second (assert with a collector over 1000 ms).
- Same isolation for `task:created`, `task:updated`, `task:deleted`, `presence:update`.
- Presence: B connects → A gets `presence:update` with B online; B opens a second tab and closes one → still online; closes both → offline. Simulate network loss by destroying the transport without a close frame → offline within 20 s.
- Presence list for tenant X never includes users who only belong to tenant Y.
- Revocation: remove B from the branch → B receives `access:revoked` and stops receiving task events.
- Rolled-back write publishes nothing (reuse the failure injection from Phase 5).
- Token expiry disconnects the socket at `exp`.
- Payload size: emit a 200 kB message from client → rejected by `maxHttpBufferSize`.

### Gate

Realtime suite green; manual check with two terminals using `npx wscat`-style script `scripts/ws-watch.mjs` (committed, not test code) shows events arriving for a seeded board.

---

## Phase 8 — Frontend foundation and design system

**Goal:** a restrained, human-looking visual system built on tokens, and the app shell.

### Colour palette

Warm paper background, deep teal as the single brand colour, terracotta reserved for danger and high priority. Column tints are soft and desaturated so cards stay the focus.

| Token                           | Light                 | Use                           |
| ------------------------------- | --------------------- | ----------------------------- |
| `--bg`                          | `#F5F3EE`             | app background                |
| `--surface`                     | `#FFFFFF`             | cards, panels                 |
| `--surface-2`                   | `#FAF9F6`             | column bodies, hover rows     |
| `--ink`                         | `#1E2A32`             | primary text                  |
| `--ink-2`                       | `#55626B`             | secondary text                |
| `--ink-3`                       | `#8A949B`             | placeholder, meta             |
| `--line`                        | `#E2DED5`             | borders                       |
| `--primary`                     | `#1F5C5A`             | buttons, links, focus         |
| `--primary-hover`               | `#184B49`             |                               |
| `--primary-tint`                | `#E3EFEE`             | selected, subtle fills        |
| `--todo` / `--todo-ink`         | `#E8EDF2` / `#3B4F63` | To Do column header           |
| `--progress` / `--progress-ink` | `#F6EAD0` / `#7A5A12` | In Progress header            |
| `--done` / `--done-ink`         | `#E0EEE3` / `#2F6B43` | Completed header              |
| `--danger` / `--danger-tint`    | `#B4432F` / `#F7E4DF` | errors, delete, high priority |
| `--warn`                        | `#B7791F`             | conflicts, reconnecting       |
| `--online` / `--offline`        | `#2E8B57` / `#9AA3A9` | presence dots                 |

- [ ] **8.1 `client/src/styles/tokens.css`**

```css
:root {
  --bg: #f5f3ee;
  --surface: #ffffff;
  --surface-2: #faf9f6;
  --ink: #1e2a32;
  --ink-2: #55626b;
  --ink-3: #8a949b;
  --line: #e2ded5;
  --primary: #1f5c5a;
  --primary-hover: #184b49;
  --primary-tint: #e3efee;
  --on-primary: #ffffff;
  --todo: #e8edf2;
  --todo-ink: #3b4f63;
  --progress: #f6ead0;
  --progress-ink: #7a5a12;
  --done: #e0eee3;
  --done-ink: #2f6b43;
  --danger: #b4432f;
  --danger-tint: #f7e4df;
  --warn: #b7791f;
  --online: #2e8b57;
  --offline: #9aa3a9;
  --p-high: #b4432f;
  --p-medium: #b7791f;
  --p-low: #4d7c8a;
  --radius: 6px;
  --radius-sm: 4px;
  --shadow: 0 1px 2px rgba(30, 42, 50, 0.06), 0 2px 8px rgba(30, 42, 50, 0.05);
  --font-ui: "Source Sans 3", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
  --s1: 4px;
  --s2: 8px;
  --s3: 12px;
  --s4: 16px;
  --s5: 24px;
  --s6: 32px;
  --fs-xs: 12px;
  --fs-sm: 14px;
  --fs-md: 16px;
  --fs-lg: 20px;
  --fs-xl: 28px;
}
:root[data-theme="dark"] {
  --bg: #14191d;
  --surface: #1b2227;
  --surface-2: #20282e;
  --ink: #e7ecef;
  --ink-2: #aab5bc;
  --ink-3: #7c8890;
  --line: #2c363d;
  --primary: #5fb3ae;
  --primary-hover: #7cc4bf;
  --primary-tint: #1f3534;
  --on-primary: #0f1f1e;
  --todo: #25303a;
  --todo-ink: #b9cadb;
  --progress: #3a3220;
  --progress-ink: #e8c97a;
  --done: #22352a;
  --done-ink: #9ed3af;
  --danger: #e27c68;
  --danger-tint: #3c2420;
}
```

- [ ] **8.2 Base styles** `client/src/styles/base.css`: import fonts (`@fontsource/source-sans-3/400.css`, `600.css`, `@fontsource/jetbrains-mono/400.css`), reset, `body { background: var(--bg); color: var(--ink); font: 400 var(--fs-sm)/1.5 var(--font-ui); }`, `:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }`, `@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }`.
- [ ] **8.3 Component primitives** in `client/src/components/ui/`: `Button` (primary, secondary, ghost, danger; 36px height), `TextField`, `Select`, `Avatar` (initials on a hashed muted colour from a fixed 6-colour set), `Badge`, `Toast`, `Dialog`, `Drawer`, `Spinner`, `Kbd`. Each is a small file with its own CSS module. No third-party UI kit.
- [ ] **8.4 Icons** `client/src/components/icons/`: hand-drawn inline SVGs, 16px, 1.5px stroke, `currentColor` — arrow-left, arrow-right, undo, redo, plus, close, clock, check, user, building, branch, alert, wifi-off.
- [ ] **8.5 App shell** `client/src/App.tsx`: top bar (left: the title **Real-Time Collaborative Kanban Board** in 16px 600 weight, then Organization selector and Branch switcher; right: connection status, presence stack, Undo, Redo, Activity, user menu). Routes: `/login`, `/` (workspace), `/b/:boardId`.
- [ ] **8.6 API client** `client/src/api/http.ts`

```ts
let accessToken: string | null = null;
export const setToken = (t: string | null) => {
  accessToken = t;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: any,
  ) {
    super(message);
  }
}

async function raw(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<any> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init.headers,
    },
  });
  if (
    res.status === 401 &&
    retry &&
    path !== "/auth/refresh" &&
    path !== "/auth/login"
  ) {
    if (await refresh()) return raw(path, init, false);
  }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok)
    throw new ApiError(
      res.status,
      body?.error?.code ?? "UNKNOWN",
      body?.error?.message ?? "Request failed",
      body?.error?.details,
    );
  return body;
}
export const http = {
  get: (p: string) => raw(p),
  post: (p: string, b?: unknown) =>
    raw(p, { method: "POST", body: JSON.stringify(b ?? {}) }),
  patch: (p: string, b: unknown) =>
    raw(p, { method: "PATCH", body: JSON.stringify(b) }),
  del: (p: string) => raw(p, { method: "DELETE" }),
};
```

Vite dev proxy in `vite.config.ts`: `/api` and `/socket.io` → `http://localhost:4000` (with `ws: true`).

### Tests (`client/tests/`)

- `tokens.test.ts`: parse `tokens.css`, compute WCAG contrast for the pairs (`--ink` on `--bg`, `--ink` on `--surface`, `--primary` on `--surface`, `--on-primary` on `--primary`, each `*-ink` on its tint, in light and dark) and assert ≥ 4.5.
- `hardcoded-colors.test.ts`: scan `client/src/**/*.{css,tsx}` except `tokens.css` and fail if a hex colour or `rgb(` literal appears (enforces "tokens only").
- `ui.test.tsx`: Button renders each variant, is keyboard activatable, shows disabled state; Dialog traps focus and closes on Escape; Toast auto-dismisses.
- `http.test.ts`: 401 triggers one refresh then retries once; failing refresh surfaces `UNAUTHENTICATED`.

### Gate

`npm run dev:client` shows the shell with the correct title and palette; frontend tests green.

---

## Phase 9 — Login, Organization selector, Branch switcher

**Goal:** authenticated users choose an Organization and Branch; switching Branch swaps the data without re-login.

### Steps

- [ ] **9.1 Session store** `client/src/store/session.ts` (Zustand): `user`, `workspaces`, `activeOrgId`, `activeTenantId`, `status`. The token lives only in memory (`setToken`). On app start call `/auth/refresh` to restore the session, then `/me/workspaces`.
- [ ] **9.2 Login page**: two fields (Email, Password), one button labelled **Sign in**, inline error text under the form ("Email or password is incorrect."). Left-aligned single column card, 360px wide, no illustration. Title is the product title.
- [ ] **9.3 Organization selector**: a button showing the active organization name; opens a listbox of organizations from `/me/workspaces`. Hidden label if the user has only one organization (rendered as plain text).
- [ ] **9.4 Branch switcher**: lists only branches the user is authorized for, with their role shown in small text ("Member", "Tenant Admin", "Org Admin"). Remember the last choice per user in `localStorage` as ids only (no data).
- [ ] **9.5 Switch behaviour**: selecting another branch (a) unsubscribes from the current board room, (b) clears the board store, undo/redo history and the offline queue for the previous branch, (c) loads boards for the new branch, (d) subscribes to its first board. A stale response from the previous branch must be ignored (use an incrementing `requestEpoch`).
- [ ] **9.6 Board list**: a left column or dropdown listing boards in the active branch; "New board" button visible only if `can(role,'board.create')` (client mirror of the permission table for UI hints; the server remains authoritative).
- [ ] **9.7 Empty states** with plain text: "No boards in this branch yet." and for admins a "Create board" button; for members, "Ask a Tenant Admin to create a board."

### Tests

- Store: login success populates workspaces; logout clears everything including in-memory token.
- Component: user with one branch sees no switcher dropdown; `multi@northwind.test` sees two branches; Org Admin sees all branches.
- Branch switch: response of the old branch arriving late does not overwrite the new branch's boards (simulate with delayed mock).
- Switching clears undo history and the offline queue.
- Playwright `e2e/switcher.spec.ts`: log in as `multi@northwind.test`, open Hyderabad board, see _Build Login Page_; switch to Vijayawada, Hyderabad tasks are gone from the DOM; no new login prompt appears.
- Playwright: manually navigating to a Vijayawada board URL as a Hyderabad-only user shows the "Board not found" view (server returned 404).

### Gate

Login → selector → switcher works against the seeded data; tests green.

---

## Phase 10 — Kanban board and drag and drop

**Goal:** three columns, cards, drag between and within columns, with keyboard and touch support.

### Steps

- [ ] **10.1 Board store** `client/src/store/board.ts`

```ts
interface TaskDto {
  id: string;
  columnId: string;
  title: string;
  description: string;
  assigneeId: string | null;
  priority: "low" | "medium" | "high";
  position: string;
  version: number;
  pending?: boolean;
}
interface BoardState {
  boardId: string | null;
  columns: {
    id: string;
    key: "todo" | "in_progress" | "completed";
    name: string;
  }[];
  tasks: Record<string, TaskDto>;
  order: Record<string, string[]>; // columnId -> task ids in display order
  applyServerTask(t: TaskDto): void; // ignores t if t.version <= local.version
  removeTask(id: string, version: number): void;
  load(snapshot: Snapshot): void;
}
```

`applyServerTask` is the single entry point for server truth (from REST responses, socket events and conflict payloads). It rejects any task whose `version` is not greater than the local version, so late events never regress state.

- [ ] **10.2 Layout**: three columns side by side (CSS grid, `grid-template-columns: repeat(3, minmax(280px, 1fr))`), horizontal scroll on narrow screens. Column header: coloured band using `--todo/--progress/--done`, column name from the server (`To Do`, `In Progress`, `Completed`), and the task count.
- [ ] **10.3 Card**: title (14px 600), assignee avatar, priority marker (small coloured bar on the left edge, not an emoji), `Pending` text marker while unconfirmed. Whole card is a button that opens the Task Detail panel. 1px border, 6px radius, shadow only while dragging.
- [ ] **10.4 DnD with `@dnd-kit`**: `DndContext` with `PointerSensor` (activation distance 6px), `TouchSensor` (delay 150ms), `KeyboardSensor` with `sortableKeyboardCoordinates`; `SortableContext` per column using `verticalListSortingStrategy`; `DragOverlay` for the lifted card; column bodies are droppable so empty columns accept drops. Collision detection `closestCorners`.
- [ ] **10.5 On drop** compute `(toColumnId, afterTaskId)` from the final order and call `moveTask` (Phase 12 wires optimistic update + REST). Members can drag only tasks assigned to them; other cards are non-draggable with a `title` tooltip "Only the assignee can move this task".
- [ ] **10.6 Create task**: "Add task" button at the bottom of To Do (admins only) opening an inline title field; Enter creates, Escape cancels.
- [ ] **10.7 Accessibility**: announce moves through an `aria-live="polite"` region ("Build Login Page moved to In Progress, position 1 of 2").

### Tests

- Store: `load()` builds `order` sorted by `position` with `id` tiebreak; `applyServerTask` ignores equal or lower versions; moving updates both columns' `order` arrays.
- Component: renders exactly three columns with the names from the specification; renders the three seeded tasks in To Do in position order.
- DnD (using `@dnd-kit` test utilities or keyboard simulation): space → ArrowRight → space moves a card from To Do to In Progress and calls `moveTask` with the right `afterTaskId`.
- Member cannot start a drag on an unassigned card.
- Playwright `e2e/dnd.spec.ts`: drag _Build Login Page_ To Do → In Progress → Completed with the mouse; reload; position persists. Drag _Fix API Bug_ above _Build Login Page_ inside To Do; reload; order persists.
- Playwright touch emulation: long-press drag works on a mobile viewport (390×844).

### Gate

Board interacts correctly against the real backend (still without optimistic logic, using confirmed responses); tests green.

---

## Phase 11 — Task Detail panel

**Goal:** a side panel with the full task information, editable by authorized roles.

### Steps

- [ ] **11.1** `Drawer` opens from the right (width 440px, full width under 640px). Opens on card click, on Enter when the card is focused, and from a context menu (right-click or the three-dot button on the card) with items **Open details**, **Move to…** (submenu of the other two columns), **Delete** (admins).
- [ ] **11.2** Fields: Title, Description (plain textarea with auto-height), Assigned member (select of branch members), Current status (select of the three columns; changing it uses the move API and appends to the bottom of the target column), Priority (Low, Medium, High), plus read-only meta: version (mono font), created, last updated, created by.
- [ ] **11.3** Editing: a **Save** button and **Discard** button appear when the form is dirty. Save sends `PATCH` with `expectedVersion` (the version loaded when the panel opened or last server-applied) and a new `actionId`. Fields the role cannot edit are rendered as read-only text, not disabled inputs.
- [ ] **11.4** If a newer version arrives from the server while the panel is open and the form is **not dirty**, update the fields silently. If the form **is dirty**, keep the user's edits, show an inline notice "This task was updated by {name}. Review the changes before saving." with a **Show latest** button; Save then sends the new `expectedVersion` only after the user confirms.
- [ ] **11.5** If the task is deleted while open, show "This task was deleted." and close the panel on dismiss.
- [ ] **11.6** Delete requires a confirm dialog with the task title in the text.
- [ ] **11.7** Panel traps focus, closes on Escape, restores focus to the originating card.

### Tests

- Component: all specified fields appear (title, description, assigned member, status, priority, other info).
- Member sees read-only fields for a task not assigned to them; assignee can edit status.
- Dirty-form conflict flow: simulate `applyServerTask` with a higher version while dirty → notice shown, user text preserved; Save blocked until "Show latest" is acknowledged.
- Clean-form update: fields refresh silently.
- Deleted while open → message shown.
- Playwright: two contexts, one edits description and saves; the other, with the panel open and a clean form, sees the new description within 1 second.
- Focus trap and Escape tests; focus returns to the card.

### Gate

Detail panel works end to end; tests green.

---

## Phase 12 — Real-time client, optimistic updates, conflicts

**Goal:** instant UI feedback, authoritative server reconciliation, and visible conflict handling.

### Steps

- [ ] **12.1 Socket client** `client/src/realtime/socket.ts`

```ts
import { io, Socket } from "socket.io-client";
let socket: Socket | null = null;

export function connect(getToken: () => string | null) {
  socket = io({
    path: "/socket.io",
    auth: (cb) => cb({ token: getToken() }),
    reconnection: true,
    reconnectionDelay: 500,
    reconnectionDelayMax: 8000,
    randomizationFactor: 0.5,
  });
  socket.on("connect", () => conn.set("connected"));
  socket.on("disconnect", () => conn.set("reconnecting"));
  socket.on("connect_error", (e) => {
    if (e.message === "UNAUTHENTICATED") refreshThenReconnect();
  });
  for (const ev of [
    "task:created",
    "task:updated",
    "task:moved",
    "task:reordered",
  ] as const)
    socket.on(ev, ({ task }) => board.getState().applyServerTask(task));
  socket.on("task:deleted", ({ taskId, version }) =>
    board.getState().removeTask(taskId, version),
  );
  socket.on("board:resync", () => refetchSnapshot());
  socket.on("presence:update", (p) => presence.getState().set(p));
  socket.on("access:revoked", () => session.getState().handleRevoked());
  return socket;
}
export const subscribeBoard = (boardId: string) =>
  emitAck("board:subscribe", { boardId });
```

On every `connect` (including reconnect) re-send `board:subscribe` for the open board, then refetch the snapshot (Phase 15).

- [ ] **12.2 Optimistic move** in `client/src/store/actions.ts`

```ts
export async function moveTask(
  taskId: string,
  toColumnId: string,
  afterTaskId: string | null,
) {
  const s = board.getState();
  const before = s.tasks[taskId]!;
  const snapshot = s.captureOrder(); // columns' order arrays + task copy
  const actionId = crypto.randomUUID();
  const optimisticPosition = generateKeyBetween(
    ...neighbourPositions(s, toColumnId, afterTaskId),
  );

  s.optimisticSet({
    ...before,
    columnId: toColumnId,
    position: optimisticPosition,
    pending: true,
  });
  try {
    const { data } = await api.moveTask(taskId, {
      expectedVersion: before.version,
      toColumnId,
      afterTaskId,
      actionId,
    });
    board.getState().applyServerTask({ ...data.task, pending: false });
    history.record({
      kind: "move",
      taskId,
      actionId,
      from: {
        columnId: before.columnId,
        afterTaskId: previousNeighbour(snapshot, taskId),
      },
      to: { columnId: toColumnId, afterTaskId },
      versionAfter: data.task.version,
    });
  } catch (e) {
    if (e instanceof ApiError && e.code === "VERSION_CONFLICT") {
      board.getState().forceApplyServerTask(e.details.current); // latest accepted state wins
      toast.warn(
        "This task was changed by another user. Showing the latest version.",
      );
    } else if (
      e instanceof ApiError &&
      (e.status === 403 || e.status === 404)
    ) {
      board.getState().restore(snapshot);
      toast.error("You do not have permission to move this task.");
    } else if (isNetworkError(e)) {
      offlineQueue.enqueue({
        type: "move",
        actionId,
        taskId,
        baseVersion: before.version,
        toColumnId,
        afterTaskId,
      });
      toast.info(
        "You are offline. This change is pending and has not been saved.",
      );
    } else {
      board.getState().restore(snapshot);
      toast.error("The change could not be saved.");
    }
  }
}
```

- [ ] **12.3** Same pattern for create (temporary client id replaced by the server id on response), update, delete.
- [ ] **12.4 Ignore own echoes**: socket events carrying an `actionId` already confirmed locally are no-ops because `applyServerTask` ignores `version <= local`. Events for tasks in a _pending_ local state with a lower expected version are applied only after the REST call settles (queue them per task id to avoid flicker).
- [ ] **12.5 Conflict UX**: a toast (bottom-left, plain text, 6 s) and a 1.2 s outline on the affected card in `--warn`. The card shows the server's state. No modal.
- [ ] **12.6 Connection indicator** in the top bar: dot + text, states **Connected**, **Reconnecting…**, **Offline**.

### Tests

- Store unit: optimistic move shows `pending:true` and the new column immediately; on success pending clears and version increments.
- 409: board shows the server's `current` task, toast text matches, no leftover pending flag, history not recorded.
- 403/404: previous order restored exactly (deep-equal to snapshot).
- Network error: action enqueued, UI still shows pending.
- Late socket event with lower version never overwrites a newer local task.
- Two quick successive moves of the same task: second uses the version returned by the first (serialize per-task actions through a small promise chain).
- Playwright `e2e/conflict.spec.ts` (two browser contexts, same branch, same board): both open _Fix API Bug_ in To Do; context 1 drags to In Progress and context 2 drags to Completed at the same time (`Promise.all`). Assert: both UIs end on the same final column; the loser sees the conflict toast; loser's card version equals the winner's; reload keeps the state.
- Playwright: context 2 (same branch) sees context 1's create, edit, move, reorder, delete without reload; context 3 (other branch) sees nothing (assert DOM unchanged and no socket frame received through `page.on('websocket')`).

### Gate

Two-user conflict scenario from the specification behaves exactly as described; tests green.

---

## Phase 13 — Undo and redo

**Goal:** reversible moves, reorders, edits, with validation so an undo never blindly restores an outdated state.

### Steps

- [ ] **13.1 History store** `client/src/store/history.ts`: two stacks (`undo`, `redo`), max 50 entries, cleared on branch switch, board switch and logout. Entry shape:

```ts
type HistoryEntry =
  | {
      kind: "move";
      taskId: string;
      from: Place;
      to: Place;
      versionAfter: number;
    }
  | {
      kind: "update";
      taskId: string;
      before: Partial<Fields>;
      after: Partial<Fields>;
      versionAfter: number;
    }
  | { kind: "create"; task: TaskDto }
  | { kind: "delete"; task: TaskDto };
type Place = { columnId: string; afterTaskId: string | null };
```

- [ ] **13.2 Undo = inverse command with the _current_ version**

```ts
export async function undo() {
  const entry = history.peekUndo();
  if (!entry) return;
  const t = board.getState().tasks[entry.taskId];
  if (!t || t.version !== entry.versionAfter) {
    history.dropUndo();
    toast.warn(
      "This change can no longer be undone because the task was changed by someone else.",
    );
    return;
  }
  const ok = await runInverse(entry); // moveTask(from) / patch(before) / delete(created) / re-create(deleted)
  ok ? history.commitUndo(entry) : history.dropUndo();
}
```

The local version check is a fast path; the server's `expectedVersion` check is the authority, so a race between the local check and the request is still caught (409 → same warning).

- [ ] **13.3 Redo** mirrors undo using the `to`/`after` data and the version returned by the undo.
- [ ] **13.4 Neighbour fallback**: if `from.afterTaskId` no longer exists in the column (deleted or moved by someone else), send `afterTaskId: null` only if the task itself is still at `versionAfter`; the position is then "top of column" and the toast says "Restored to the top of To Do."
- [ ] **13.5 Deleted-task undo**: re-creating a deleted task makes a **new** task (new id, version 1) at its former column/position; the activity log shows `task.created`. Redo of that deletes it. State this in `docs/README` trade-offs.
- [ ] **13.6 UI**: Undo and Redo buttons in the top bar (disabled when the stack is empty, tooltips show the action name, e.g. "Undo: moved Build Login Page"), shortcuts `Ctrl/Cmd+Z` and `Ctrl/Cmd+Shift+Z` (ignored while typing in an input or textarea).
- [ ] **13.7** Undo/redo actions go through the same optimistic path, carry their own `actionId`, are logged in `activity_logs` like any other action, and are broadcast to others.

### Tests

- History: records after confirmed success only; max 50; cleared on branch switch.
- Move → undo → task back at the original column and neighbour; redo → in In Progress again.
- Another user moves the task after your move → your undo is refused with the specified message; stacks consistent (entry dropped, redo untouched).
- Undo racing a remote change (local check passes, server returns 409) → same warning, no state corruption.
- Update description → undo restores previous description; if another user changed the description meanwhile, undo is refused.
- Delete → undo creates a new task at the former place; redo deletes it.
- Keyboard shortcuts work and are ignored inside text fields.
- Playwright: accidental drag to Completed, press `Ctrl+Z`, task back in To Do, the other user's board also shows it back.

### Gate

Undo/redo suite green, including the two-user refusal case.

---

## Phase 14 — Presence and Activity UI

### Steps

- [ ] **14.1 Presence stack** in the top bar: up to 5 avatars (initials) with a 8px status dot (`--online` or `--offline`), `+N` overflow; tooltip lists names with "Online"/"Offline". Online users sorted first. Data from `presence:update`, scoped to the active branch only; cleared on switch.
- [ ] **14.2 Activity drawer** (button "Activity" in the top bar): list newest first with infinite scroll (`cursor`), each row: avatar, sentence ("Priya moved Fix API Bug from To Do to In Progress"), relative time with the exact timestamp in the `title` attribute. Filters: this board / this task. New entries stream in live (append `activity` events: add a `activity:created` event to the contract and publish it with the same after-commit rule).
- [ ] **14.3** Sentences are built from structured `before/after` through a pure function `describeActivity(entry)`, with one template per action type.

### Tests

- `describeActivity` table test for every action type (including missing actor → "A former member").
- Presence UI: online user first; offline dot colour; overflow count; list resets on branch switch.
- Activity drawer: pagination loads next page at scroll end; new live entry appears at top without duplicating.
- Playwright: user B comes online → A's stack shows B online; B closes the tab → offline within 20 s; activity entry appears live after B moves a task.
- Backend addition test: `activity:created` is delivered only to the tenant's board room.

### Gate

Presence and activity verified in two browsers.

---

## Phase 15 — Network recovery

**Goal:** the pending-action queue with reconnection and reconciliation described in the edge-case document.

### Steps

- [ ] **15.1 Connection state machine** `client/src/realtime/connection.ts`: `connected → reconnecting → offline` using Socket.IO events plus `navigator.onLine` and a 5 s `HEAD /healthz` probe when the socket is down. Indicator updates immediately.
- [ ] **15.2 Persistent queue** `client/src/store/offlineQueue.ts` using `idb-keyval`, keyed per `userId:tenantId`:

```ts
interface QueuedAction {
  actionId: string;
  type: "move" | "update" | "create" | "delete";
  taskId?: string;
  baseVersion: number;
  payload: unknown;
  queuedAt: number;
  status: "pending" | "conflict" | "failed";
}
```

Actions are stored in order. The queue is cleared on logout.

- [ ] **15.3 Offline behaviour**: while offline, supported actions (move, reorder, edit, create, delete) are applied optimistically with the `Pending` marker and queued. A banner reads "You are offline. Changes are pending and are not saved yet." Nothing is described as saved.
- [ ] **15.4 Recovery sequence** (strict order)
  1. Socket reconnects (refresh token first if expired).
  2. Re-send `board:subscribe`.
  3. Fetch the full snapshot `GET /boards/:id` and `board.load()` it, but keep pending local overlays.
  4. Replay queued actions **in order**, one at a time, each with its original `actionId` and `expectedVersion = baseVersion`.
  5. For each response: success → mark confirmed and apply the server task; `409` → mark `conflict`, apply the server's current task, collect for the summary; `403/404` → `failed`; network error → stop and retry later.
  6. When the queue is empty show a summary toast: "3 changes saved. 1 change could not be applied because the task was changed by someone else." with a **Review** button listing conflicted items (title, what you tried, current state) and a **Retry** action that re-issues the change using the current version after the user confirms.
- [ ] **15.5 Idempotency**: because each queued item keeps its `actionId`, a request that reached the server but whose response was lost is replayed safely; the server returns the stored result without writing again.
- [ ] **15.6 Reload while offline with pending items**: the queue is restored from IndexedDB on startup; the UI shows the pending count and attempts recovery once online.
- [ ] **15.7 Coalescing**: consecutive queued moves of the same task are collapsed into one (first `baseVersion`, last target) to reduce conflicts.

### Tests

- Queue unit: ordering preserved; persisted and restored across a simulated reload; scoped per user and tenant; cleared on logout.
- Coalescing: three moves of the same task become one with the first `baseVersion`.
- Recovery order test with a mocked API: asserts calls happen as snapshot → replay in order; stops on network error and resumes.
- Conflict during replay: other user changed the task while offline → item marked `conflict`, server state shown, summary toast text correct, Retry uses the new version.
- Lost-response replay: server processed the request but the client saw a network error → replay returns `replayed` result and no duplicate activity row (backend test with a fake proxy dropping the response).
- Never shows "Saved" for pending items (assert marker visible until confirmation).
- Playwright `e2e/offline.spec.ts`: `context.setOffline(true)`, move a card, banner appears, marker shown; other context moves the same card; `setOffline(false)`; the offline user sees a conflict summary and the board equals the server state.
- Playwright: reload while offline-with-pending keeps the pending count.

### Gate

Network recovery scenario passes in the browser.

---

## Phase 16 — Edge-case suite

**Goal:** one consolidated, repeatable proof for each of the five specified edge cases. Tests live under `server/tests/edge/` and `e2e/edge/` (git-ignored).

### 16.1 Cross-tenant data leakage

Parametrized matrix. For every route in section "Routes" (Phase 4) and every socket event, issue the request as a user of Hyderabad targeting a resource of Vijayawada, by (a) changing the path id, (b) putting the foreign id in the body (`columnId`, `afterTaskId`, `assigneeId`, `tenantId`), (c) putting it in the query string. Expected: 404 (or 400 for foreign ids in bodies); response bodies and timings do not reveal existence (compare status and body shape between "nonexistent id" and "foreign id").
Extra checks: SQL injection strings in ids rejected by Zod; `app.tenant_id` unset → RLS returns zero rows even for a hand-written query via the app role; forging a JWT with another `sub` fails signature check.

### 16.2 Cross-organization isolation

Same matrix between Northwind and Contoso, including activity logs, presence lists, member lookups by email (adding a Contoso user to a Northwind branch must be explicit by an authorized admin and must not leak which emails exist: always return the same message), cached responses (set `Cache-Control: no-store` on all `/api/v1` responses and assert it), and socket broadcasts.

### 16.3 Concurrent edits

Description edit vs status move, two description edits, edit vs delete, edit vs assign. Assert one winner, one 409 with `current`, loser retry works, final state equals the serial application of the winner then the retried loser.

### 16.4 Drag-and-drop conflicts

- Spec scenario (To Do → In Progress vs To Do → Completed).
- Two users reorder the same column simultaneously (10 random reorders each, interleaved): final order is a valid permutation, identical for both clients after sync, no duplicate or lost tasks.
- Different tasks dropped into the same slot: both appear, order deterministic.
- Move into a column while the target neighbour is deleted by someone else → server uses fresh neighbours, still succeeds or returns a clear 400 for a vanished `afterTaskId` (client then retries with `null` after refetch).

### 16.5 Network recovery

The Phase 15 scenarios plus: token expires during offline period (refresh then replay), server restart while clients are connected (clients reconnect, resubscribe, resync), 30 queued actions replay in order.

### Extra robustness

- Load test script (committed in `scripts/`, uses `autocannon`, no test code): 200 concurrent sockets over 5 tenants, 20 moves/second; p95 move latency under 150 ms on a laptop, zero cross-tenant deliveries (counted by the harness).
- Chaos: kill the DB connection mid-move; the API returns 500 `INTERNAL`, no partial write (task version unchanged, no activity row).

### Gate

All edge suites green three times in a row.

---

## Phase 17 — Documentation deliverables

Produce these files; they are committed (unlike tests).

- [ ] **17.1 `docs/ER.md`** — Mermaid ER diagram plus a short explanation of the composite foreign keys that make cross-tenant references impossible.

```mermaid
erDiagram
  organizations ||--o{ tenants : has
  organizations ||--o{ memberships : has
  tenants ||--o{ memberships : "scopes (non org_admin)"
  users ||--o{ memberships : has
  tenants ||--o{ boards : owns
  boards ||--|{ columns : has
  columns ||--o{ tasks : contains
  boards ||--o{ tasks : contains
  users ||--o{ tasks : "assigned"
  tenants ||--o{ activity_logs : records
  users ||--o{ activity_logs : performs
```

Export a PNG/SVG of the diagram as well (`docs/er-diagram.svg`) for graders who do not render Mermaid.

- [ ] **17.2 `README.md`** with the exact sections: Overview (use the project description text), Architecture (diagram of client ↔ REST ↔ Postgres, client ↔ Socket.IO rooms), **Tenancy model** (hierarchy, `tenant_id` on all business data, resolution from the resource, RLS second layer, 404-not-403 policy, room naming), **Concurrency** (OCC with versions, row lock, idempotency keys, why not pessimistic locking, why not rely on WebSocket events), **Ordering** (fractional indexing, rebalance), **Real-time** (WebSocket vs SSE decision, rooms, presence, scale-out with Redis), **Undo/redo** (validation approach and limitation for deleted tasks), **Network recovery**, **Trade-offs and limitations**, **Running locally**, **Environment variables**, **Project structure**, **Security checklist**, **Testing** (explain tests exist locally, are git-ignored by project choice, and list the commands).
- [ ] **17.3 `docs/API.md`** — every route from Phase 4/5/6: method, path, permission, request body, response, error codes, example `curl`.
- [ ] **17.4 `docs/WEBSOCKET.md`** — handshake, auth, rooms, events table from Phase 7 (plus `activity:created`), ack shapes, reconnect and resync procedure, presence semantics.
- [ ] **17.5 `docs/DECISIONS.md`** — short ADR entries: Socket.IO over SSE; OCC over pessimistic locking; fractional indexing over integer positions; raw SQL over ORM; RLS in addition to application checks; tokens not carrying roles.

### Tests

- Local script `scripts/test-docs.sh` (git-ignored by pattern) that checks every route registered in Express appears in `docs/API.md` (dump routes from the app, grep the doc) and every emitted event name appears in `docs/WEBSOCKET.md`. Fails on any missing entry.

### Gate

Docs complete; doc-coverage script passes.

---

## Phase 18 — Production hardening and deployment

### Steps

- [ ] **18.1 Server hardening**: `helmet` with CSP for the API; `app.set("trust proxy", 1)` behind a reverse proxy; `Cache-Control: no-store` for `/api/v1`; request timeout 15 s; `express-rate-limit` general limit (300/min/IP) plus the stricter auth limits; pg pool timeouts (`connectionTimeoutMillis: 5000`, `statement_timeout: 10000` per connection via `options`); graceful shutdown on `SIGTERM` (stop accepting, `io.close()`, drain, `pool.end()`).
- [ ] **18.2 Dockerfiles**

```dockerfile
# server/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY server/package.json server/
RUN npm ci -w server --include-workspace-root
COPY server server
RUN npm run build -w server

FROM node:20-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/package.json /app/package-lock.json ./
COPY --from=build /app/server/package.json server/
RUN npm ci -w server --omit=dev --include-workspace-root
COPY --from=build /app/server/dist server/dist
COPY server/migrations server/migrations
USER node
WORKDIR /app/server
CMD ["sh", "-c", "node dist/db/migrate.js && node dist/index.js"]
```

```dockerfile
# client/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY client/package.json client/
RUN npm ci -w client --include-workspace-root
COPY client client
RUN npm run build -w client

FROM nginx:1.27-alpine
COPY client/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/client/dist /usr/share/nginx/html
```

`client/nginx.conf`: serve the SPA with `try_files $uri /index.html`, proxy `/api/` and `/socket.io/` to `server:4000` with `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`, add long cache headers for hashed assets, `Cache-Control: no-store` for `index.html`.

- [ ] **18.3 `docker-compose.yml`** (production-like): `db` (postgres:16, volume), `redis`, `server`, `client` on port 8080; secrets from `.env`; healthchecks (`pg_isready`, `/readyz`); the server waits for the DB healthcheck. The DB bootstrap creates the owner user and `kanban_app` role; migration `002` sets `kanban_app` password from the `APP_DB_PASSWORD` env through `psql` variable substitution in the entrypoint (replace the hard-coded `app_pw` with a placeholder rendered at deploy time; never ship the dev password).
- [ ] **18.4 Frontend production polish**: code-split routes, `<meta name="viewport">`, favicon (a simple three-column glyph drawn as SVG), document title `Real-Time Collaborative Kanban Board`, error boundary with a plain "Something went wrong. Reload the page." and a Reload button, no source maps in production, `Content-Security-Policy` meta/headers allowing only self plus the socket origin.
- [ ] **18.5 CI** `.github/workflows/ci.yml`: install, lint, typecheck, build server and client, build Docker images. (Test jobs are optional locally because test code is git-ignored by project choice; if tests are later committed, add a job with a Postgres service.)
- [ ] **18.6 Observability**: structured logs with request id and `userId`/`tenantId` on every log line after auth; `GET /metrics` (Prometheus text, protected by a bearer token from env) with counters for HTTP requests, 409 conflicts, active sockets per process, activity rows written.
- [ ] **18.7 Backups and data hygiene**: document `pg_dump` schedule in README; `processed_actions` cleanup already scheduled; add `ANALYZE` after seed.
- [ ] **18.8 Dependency and secret hygiene**: `npm audit --omit=dev` clean for high and critical; `git secrets`-style grep script `scripts/check-secrets.sh` (committed) failing on committed `.env`, private keys or the dev passwords.

### Tests (local, ignored)

- `scripts/test-prod-smoke.sh`: `docker compose up -d --build`, wait for health, run: register/login via curl, create board, open two sockets and confirm an event, restart the `server` container and confirm clients reconnect, then `docker compose down -v`.
- Security header check: `curl -I` asserts `x-content-type-options`, `content-security-policy`, `strict-transport-security` (behind TLS), no `x-powered-by`.
- Image check: container runs as non-root (`docker exec server id -u` ≠ 0).
- Graceful shutdown: send `SIGTERM` during an in-flight move; request completes and the process exits 0.
- Lighthouse run on the login and board pages: accessibility ≥ 95, best-practices ≥ 95.

### Gate

`docker compose up --build` from a clean clone with only a filled `.env` serves a working app at `http://localhost:8080`.

---

## Phase 19 — Final acceptance

Walk through this checklist and attach evidence (terminal output or screenshots) in the PR description. Mapped to the evaluation criteria.

**Architecture (30%)**

- [ ] Modular server (`auth`, `organizations`, `tenants`, `boards`, `columns`, `tasks`, `activity`, `realtime`, `access`); no business logic in routes
- [ ] Tenancy model documented and enforced in three layers: route guards, `withTenant` + SQL filters, Row Level Security
- [ ] Hierarchy Organization → Tenants → Boards in schema and API

**Correctness (20%)**

- [ ] All five edge-case suites green three consecutive times
- [ ] Spec scenario _Fix API Bug_ produces one winner, one conflict, consistent final state for both users

**Database design (15%)**

- [ ] All eight tables present; every business table has `tenant_id`; composite FKs prevent cross-tenant links
- [ ] Task ordering via fractional index with covering index; version column on tasks

**Frontend quality (15%)**

- [ ] Organization selector, Branch switcher, Kanban with drag and drop (mouse, touch, keyboard), Task Detail panel, live updates
- [ ] UI uses tokens only, specification wording only, no generated-looking copy or decoration
- [ ] Lighthouse accessibility ≥ 95; contrast test passes

**Advanced thinking (20%)**

- [ ] Presence with heartbeats, tenant-scoped rooms, optimistic UI with rollback, undo/redo with validation, tenant activity logs, OCC with idempotency keys, offline queue with reconciliation
- [ ] Scale-out path documented and verified with Redis adapter enabled (run two server instances behind the nginx proxy and confirm events cross instances)
- [ ] Load script results recorded in README

**Deliverables**

- [ ] Backend + real-time server
- [ ] Frontend UI
- [ ] Database schema (ER diagram in `docs/ER.md` and `docs/er-diagram.svg`)
- [ ] README (architecture, tenancy model, trade-offs)
- [ ] API + WebSocket documentation

**Repository hygiene**

- [ ] `git ls-files | grep -Ei "test|spec|e2e|vitest|playwright|coverage"` prints nothing
- [ ] No `.env`, no secrets, no `console.log`, no TODO
- [ ] Fresh clone builds and runs with `docker compose up --build`
