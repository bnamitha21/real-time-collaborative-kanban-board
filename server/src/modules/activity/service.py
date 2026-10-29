from typing import Any

from psycopg import Connection

from server.src.db.pool import with_tenant
from server.src.modules.boards.service import decode_cursor, encode_cursor


def list_tenant_activity(
    tenant_id: str,
    board_id: str | None = None,
    task_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], str | None]:
    def _list(conn: Connection) -> tuple[list[dict[str, Any]], str | None]:
        with conn.cursor() as cur:
            fetch_count = limit + 1
            conditions = ["a.tenant_id = %s"]
            params: list[Any] = [tenant_id]

            if board_id:
                conditions.append("a.board_id = %s")
                params.append(board_id)

            if task_id:
                conditions.append("a.task_id = %s")
                params.append(task_id)

            if cursor:
                dt, row_id = decode_cursor(cursor)
                conditions.append("(a.created_at < %s OR (a.created_at = %s AND a.id < %s))")
                params.extend([dt, dt, int(row_id)])

            where_clause = " AND ".join(conditions)
            params.append(fetch_count)

            query = f"""
                SELECT a.id, a.organization_id, a.tenant_id, a.board_id, a.task_id,
                       a.actor_id, u.name AS actor_name, a.action, a.before_value,
                       a.after_value, a.created_at
                FROM activity_logs a
                LEFT JOIN users u ON u.id = a.actor_id
                WHERE {where_clause}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT %s;
            """
            cur.execute(query, params)
            rows = cur.fetchall()

            has_next = len(rows) > limit
            items = rows[:limit]

            next_cursor = None
            if has_next and items:
                last_dt = items[-1][10]
                last_id = str(items[-1][0])
                next_cursor = encode_cursor(last_dt, last_id)

            activities = [
                {
                    "id": str(r[0]),
                    "organizationId": str(r[1]),
                    "tenantId": str(r[2]),
                    "boardId": str(r[3]) if r[3] else None,
                    "taskId": str(r[4]) if r[4] else None,
                    "actorId": str(r[5]) if r[5] else None,
                    "actorName": r[6] if r[6] else "System",
                    "action": r[7],
                    "before": r[8],
                    "after": r[9],
                    "createdAt": r[10].isoformat() if hasattr(r[10], "isoformat") else str(r[10]),
                }
                for r in items
            ]
            return activities, next_cursor

    return with_tenant(tenant_id, _list)


def cleanup_processed_actions(conn: Connection, days: int = 7) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM processed_actions WHERE created_at < now() - (%s || ' days')::interval;",
            (days,),
        )
        return cur.rowcount
