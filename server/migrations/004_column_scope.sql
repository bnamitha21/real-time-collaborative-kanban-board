CREATE OR REPLACE FUNCTION column_scope(p_id uuid)
RETURNS TABLE (tenant_id uuid, board_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$ SELECT c.tenant_id, c.board_id FROM columns c WHERE c.id = p_id $$;

REVOKE ALL ON FUNCTION column_scope(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION column_scope(uuid) TO kanban_app;
