-- 002_rls.sql — Row Level Security and restricted application role
--
-- The kanban_app role runs all application queries.
-- It does NOT own the tables, so PostgreSQL RLS policies apply to it.
-- The owner role (which does own the tables) bypasses RLS — used only for
-- migrations and seed scripts, never for request handling.
--
-- RLS design: every tenant-scoped table has a `tenant_id` column.
-- The app sets `app.tenant_id` via SET_CONFIG before querying.
-- Without a tenant set, nullif(...)::uuid is NULL → no rows match (fails closed).

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kanban_app') THEN
    CREATE ROLE kanban_app LOGIN PASSWORD 'app_pw';
  END IF;
END $$;

-- Grant schema and table access to the app role
GRANT USAGE ON SCHEMA public TO kanban_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kanban_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kanban_app;

-- Ensure future tables also grant access (ALTER DEFAULT PRIVILEGES applies to owner's future objects)
ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO kanban_app;
ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO kanban_app;

-- The app role must never access the migrations tracking table
REVOKE ALL ON schema_migrations FROM kanban_app;

-- ---- Enable Row Level Security ----
ALTER TABLE boards            ENABLE ROW LEVEL SECURITY;
ALTER TABLE columns           ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks             ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_actions ENABLE ROW LEVEL SECURITY;

-- ---- Tenant isolation policies ----
-- Using USING + WITH CHECK ensures both reads and writes are scoped to the tenant.
-- nullif(current_setting('app.tenant_id', true), '') returns NULL when not set,
-- making the condition FALSE for all rows — a secure "fail closed" default.

DROP POLICY IF EXISTS tenant_isolation ON boards;
CREATE POLICY tenant_isolation ON boards
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON columns;
CREATE POLICY tenant_isolation ON columns
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON tasks;
CREATE POLICY tenant_isolation ON tasks
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON activity_logs;
CREATE POLICY tenant_isolation ON activity_logs
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON processed_actions;
CREATE POLICY tenant_isolation ON processed_actions
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
