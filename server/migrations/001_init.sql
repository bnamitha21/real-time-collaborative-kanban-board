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
CREATE OR REPLACE TRIGGER organizations_touch BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE OR REPLACE TRIGGER tenants_touch       BEFORE UPDATE ON tenants       FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE OR REPLACE TRIGGER boards_touch        BEFORE UPDATE ON boards        FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE OR REPLACE TRIGGER tasks_touch         BEFORE UPDATE ON tasks         FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
