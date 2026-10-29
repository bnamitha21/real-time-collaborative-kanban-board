from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g
from psycopg import Connection

from server.src.db.pool import with_tenant, with_tx
from server.src.lib.errors import forbidden, not_found, unauthenticated
from server.src.modules.access.access import TenantAccess, resolve_org_role, resolve_tenant_access
from server.src.modules.access.permissions import can


def load_board_scope(board_id: str, conn: Connection | None = None) -> tuple[str, str] | None:
    def _query(c: Connection) -> tuple[str, str] | None:
        with c.cursor() as cur:
            cur.execute("SELECT tenant_id, organization_id FROM board_scope(%s);", (board_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return str(row[0]), str(row[1])

    if conn is not None:
        return _query(conn)
    return with_tx(_query)


def load_column_scope(column_id: str, conn: Connection | None = None) -> tuple[str, str] | None:
    def _query(c: Connection) -> tuple[str, str] | None:
        with c.cursor() as cur:
            cur.execute("SELECT tenant_id, board_id FROM column_scope(%s);", (column_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return str(row[0]), str(row[1])

    if conn is not None:
        return _query(conn)
    return with_tx(_query)


def load_task_scope(task_id: str, conn: Connection | None = None) -> tuple[str, str] | None:
    def _query(c: Connection) -> tuple[str, str] | None:
        with c.cursor() as cur:
            cur.execute("SELECT tenant_id, board_id FROM task_scope(%s);", (task_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return str(row[0]), str(row[1])

    if conn is not None:
        return _query(conn)
    return with_tx(_query)


def require_org_access(perm: str) -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = getattr(g, "user_id", None)
            if not user_id:
                raise unauthenticated("Authentication required")

            org_id = kwargs.get("org_id") or kwargs.get("orgId")
            if not org_id:
                raise not_found("Organization not found")

            role = resolve_org_role(user_id, str(org_id))
            if not role:
                # 404 to avoid leaking existence of organizations the caller has no membership in
                raise not_found("Organization not found")

            if perm in ("org.update", "org.delete", "tenant.create") and role != "org_admin":
                raise forbidden("You do not have permission to perform this action")

            g.org_id = str(org_id)
            g.org_role = role
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_tenant_access(perm: str) -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = getattr(g, "user_id", None)
            if not user_id:
                raise unauthenticated("Authentication required")

            tenant_id = kwargs.get("tenant_id") or kwargs.get("tenantId")
            board_id = kwargs.get("board_id") or kwargs.get("boardId")
            column_id = kwargs.get("column_id") or kwargs.get("columnId")
            task_id = kwargs.get("task_id") or kwargs.get("taskId")

            if not tenant_id and board_id:
                scope = load_board_scope(board_id)
                if not scope:
                    raise not_found("Board not found")
                tenant_id = scope[0]

            elif not tenant_id and column_id:
                scope = load_column_scope(column_id)
                if not scope:
                    raise not_found("Column not found")
                tenant_id = scope[0]

            elif not tenant_id and task_id:
                scope = load_task_scope(task_id)
                if not scope:
                    raise not_found("Task not found")
                tenant_id = scope[0]

            if not tenant_id:
                raise not_found("Tenant not found")

            access: TenantAccess | None = resolve_tenant_access(user_id, str(tenant_id))
            if not access:
                # 404 to avoid leaking existence of other tenants' resources
                raise not_found("Resource not found")

            ctx: dict[str, Any] = {}
            # If checking task update/move, check assignee status for member:own
            if task_id and access.role == "member":

                def _check_assignee(c: Connection) -> bool:
                    with c.cursor() as cur:
                        cur.execute(
                            "SELECT assignee_id FROM tasks WHERE id = %s AND tenant_id = %s;",
                            (task_id, tenant_id),
                        )
                        r = cur.fetchone()
                        return bool(r and str(r[0]) == str(user_id))

                ctx["is_assignee"] = with_tenant(str(tenant_id), _check_assignee)

            if not can(access.role, perm, ctx):
                raise forbidden("You do not have permission to perform this action")

            g.access = access
            g.tenant_id = str(tenant_id)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
