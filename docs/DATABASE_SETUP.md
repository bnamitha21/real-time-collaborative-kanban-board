# Database Setup Guide — Local PostgreSQL with Row Level Security

This project uses **local PostgreSQL 16** as its database with full **Row Level Security (RLS)** enforced at the database level. Docker has been removed from the setup in favor of native, local PostgreSQL execution and visual management via **pgAdmin 4**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  PostgreSQL (local :5432)                │
│                                                          │
│  Database: kanban                                        │
│                                                          │
│  Roles:                                                  │
│    owner      → runs migrations, owns tables             │
│    kanban_app → app queries (RLS enforced)               │
│                                                          │
│  Tables with RLS:                                        │
│    boards, columns, tasks,                               │
│    activity_logs, processed_actions                      │
│                                                          │
│  Tables without RLS (identity/structure):               │
│    users, organizations, tenants, memberships,           │
│    refresh_tokens, schema_migrations                     │
└─────────────────────────────────────────────────────────┘
```

### Row Level Security Design

Every tenant-scoped table has a `tenant_id` column and a PostgreSQL policy:

```sql
CREATE POLICY tenant_isolation ON boards
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
```

- The **`kanban_app`** role does NOT own the tables → RLS applies to it.
- The **`owner`** role owns the tables → RLS is bypassed (for migrations/seed only).
- The app sets `app.tenant_id` via `SELECT set_config(...)` before every tenant query.
- Without `app.tenant_id` set: `nullif(...)::uuid` → `NULL` → **no rows match** (fails closed).

---

## Quick Start Commands

You can control PostgreSQL and setup tasks directly via npm or Python:

| Command | Action |
|---|---|
| `npm run db:status` | Check if PostgreSQL server is running on port `5432` |
| `npm run db:start` | Start local PostgreSQL server |
| `npm run db:stop` | Stop local PostgreSQL server |
| `npm run db:setup` | Run database initialization, migrations, and seed data |
| `npm run db:migrate` | Apply SQL migrations |
| `npm run db:seed` | Seed development accounts and initial board |

---

## Initializing the Database

### Option A: Using Python (Cross-platform)

```bash
# Initialize database, create roles, run migrations, and seed data
python scripts/init_db.py --seed

# If your postgres superuser has a custom password:
python scripts/init_db.py --pg-password yourpassword --seed

# Reset and re-seed (DESTRUCTIVE — clears existing data):
python scripts/init_db.py --reset --seed
```

### Option B: Using PowerShell (Windows)

```powershell
# Setup with development seed data
.\scripts\setup_db.ps1 -Seed

# Reset and re-seed
.\scripts\setup_db.ps1 -Seed -Reset
```

---

## Viewing Data in pgAdmin 4

pgAdmin 4 is installed alongside PostgreSQL. You can use it to visually browse tables, run SQL queries, and monitor real-time database activity:

1. Open **pgAdmin 4** from your Windows Start Menu.
2. Enter your master password (set during installation, typically `postgres`).
3. In the left **Object Explorer** panel, expand:
   - **`Servers`** ➔ **`PostgreSQL 16`** ➔ **`Databases`** ➔ **`kanban`**
4. Under **`kanban`**, navigate to:
   - **`Schemas`** ➔ **`public`** ➔ **`Tables`**
5. You will see all 11 tables:
   - `activity_logs`, `boards`, `columns`, `memberships`, `organizations`, `processed_actions`, `refresh_tokens`, `schema_migrations`, `tasks`, `tenants`, `users`
6. **To View Table Data**: Right-click on any table (e.g., `tasks` or `boards`) ➔ **View/Edit Data** ➔ **All Rows**.
7. In **`Login/Group Roles`**, verify:
   - `owner`: Role with CREATEDB / CREATEROLE privileges used for migrations.
   - `kanban_app`: Restricted login role used by the web server to enforce RLS.

---

## Environment Variables

Ensure `.env` in the project root is configured as follows:

```dotenv
# Migrations & seed run as owner (bypasses RLS)
DATABASE_URL_OWNER=postgresql://owner:owner_pw@localhost:5432/kanban

# Application queries run as kanban_app (RLS enforced)
DATABASE_URL=postgresql://kanban_app:app_pw@localhost:5432/kanban

# Authentication
JWT_ACCESS_SECRET=super_secret_access_key_12345_must_be_32_characters_minimum
JWT_ACCESS_TTL_SECONDS=900
REFRESH_TTL_DAYS=14

# Server Config
FLASK_ENV=development
PORT=4000
CLIENT_ORIGIN=http://localhost:5173
```

---

## Migration Files

Located in `server/migrations/`, applied in order:

| File | Description |
|------|-------------|
| `001_init.sql` | Core tables: users, organizations, tenants, memberships, boards, columns, tasks, activity_logs, processed_actions |
| `002_rls.sql` | Creates `kanban_app` role, enables Row Level Security, and applies default privileges |
| `003_scope_fns.sql` | Helper functions: `board_scope()`, `task_scope()` |
| `004_column_scope.sql` | Helper function: `column_scope()` |

Migration tracking table: `schema_migrations` (idempotent, records each applied script).

---

## Development Seed Accounts

All accounts use password: **`Passw0rd!`**

| Email | Role | Organization | Branch |
|-------|------|-------------|--------|
| `orgadmin@northwind.test` | org_admin | Northwind Traders | All branches |
| `admin.hyd@northwind.test` | tenant_admin | Northwind Traders | Hyderabad |
| `member.hyd@northwind.test` | member | Northwind Traders | Hyderabad |
| `member2.hyd@northwind.test` | member | Northwind Traders | Hyderabad |
| `admin.vja@northwind.test` | tenant_admin | Northwind Traders | Vijayawada |
| `admin@contoso.test` | org_admin | Contoso Retail | Chennai |
| `multi@northwind.test` | member | Northwind Traders | Hyderabad & Vijayawada |

---

## Verifying the Setup

```powershell
# 1. Check server health
Invoke-RestMethod http://localhost:4000/healthz

# 2. Check DB readiness
Invoke-RestMethod http://localhost:4000/readyz

# 3. Run full smoke test
powershell -ExecutionPolicy Bypass -File .\scripts\smoke.ps1
```

---

## Troubleshooting

### "Permission denied (0x0000271D/10013) or Connection Refused"
The PostgreSQL service is stopped. Start it:
```powershell
Get-Service -Name "postgresql*" | Start-Service
# or
npm run db:start
```

### "FATAL: password authentication failed for user 'postgres'"
Pass your custom password when initializing:
```powershell
python scripts/init_db.py --pg-password yourpassword --seed
```

### RLS Not Enforcing
Ensure request handlers connect using `DATABASE_URL` (`kanban_app` user), never `DATABASE_URL_OWNER`.
