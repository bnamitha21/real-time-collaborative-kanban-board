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

DROP POLICY IF EXISTS tenant_isolation ON boards;
CREATE POLICY tenant_isolation ON boards            USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON columns;
CREATE POLICY tenant_isolation ON columns           USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON tasks;
CREATE POLICY tenant_isolation ON tasks             USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON activity_logs;
CREATE POLICY tenant_isolation ON activity_logs     USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation ON processed_actions;
CREATE POLICY tenant_isolation ON processed_actions USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                                                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
