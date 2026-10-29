CREATE OR REPLACE FUNCTION board_scope(p_id uuid)
RETURNS TABLE (tenant_id uuid, organization_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$ SELECT b.tenant_id, b.organization_id FROM boards b WHERE b.id = p_id $$;

CREATE OR REPLACE FUNCTION task_scope(p_id uuid)
RETURNS TABLE (tenant_id uuid, board_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$ SELECT t.tenant_id, t.board_id FROM tasks t WHERE t.id = p_id $$;

REVOKE ALL ON FUNCTION board_scope(uuid), task_scope(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION board_scope(uuid), task_scope(uuid) TO kanban_app;

