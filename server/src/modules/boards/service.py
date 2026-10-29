import base64
from datetime import datetime
from typing import Any

from psycopg import Connection
from server.src.db.pool import with_tenant
from server.src.lib.errors import bad_request, not_found
from server.src.modules.activity.log import log_activity


def encode_cursor(dt: datetime, row_id: str) -> str:
    val = f"{dt.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(val.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        dt_str, row_id = raw.split("|", 1)
        return datetime.fromisoformat(dt_str), row_id
    except (ValueError, TypeError, UnicodeDecodeError):
        raise bad_request("Invalid cursor") from None


def create_board(org_id: str, tenant_id: str, user_id: str, name: str) -> dict[str, Any]:
    def _create(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO boards (organization_id, tenant_id, name, created_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id, organization_id, tenant_id, name, created_at, updated_at;
                """,
                (org_id, tenant_id, name, user_id),
            )
            row = cur.fetchone()
            if not row:
                raise bad_request("Failed to create board")

            board_id = str(row[0])
            board = {
                "id": board_id,
                "organizationId": str(row[1]),
                "tenantId": str(row[2]),
                "name": row[3],
                "createdAt": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                "updatedAt": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            }

            cols = [
                ("todo", "To Do", 0),
                ("in_progress", "In Progress", 1),
                ("completed", "Completed", 2),
            ]
            for key, col_name, pos in cols:
                cur.execute(
                    """
                    INSERT INTO columns (tenant_id, board_id, key, name, position)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (tenant_id, board_id, key, col_name, pos),
                )

            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action="board.created",
                board_id=board_id,
                after={"name": name},
            )
            return board

    return with_tenant(tenant_id, _create)


def list_boards(
    tenant_id: str, limit: int = 50, cursor: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    def _list(conn: Connection) -> tuple[list[dict[str, Any]], str | None]:
        with conn.cursor() as cur:
            fetch_count = limit + 1
            if cursor:
                dt, row_id = decode_cursor(cursor)
                cur.execute(
                    """
                    SELECT id, organization_id, tenant_id, name, created_at, updated_at
                    FROM boards
                    WHERE tenant_id = %s
                      AND (created_at < %s OR (created_at = %s AND id < %s))
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (tenant_id, dt, dt, row_id, fetch_count),
                )
            else:
                cur.execute(
                    """
                    SELECT id, organization_id, tenant_id, name, created_at, updated_at
                    FROM boards
                    WHERE tenant_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (tenant_id, fetch_count),
                )

            rows = cur.fetchall()
            has_next = len(rows) > limit
            items = rows[:limit]

            next_cursor = None
            if has_next and items:
                last_dt = items[-1][4]
                last_id = str(items[-1][0])
                next_cursor = encode_cursor(last_dt, last_id)

            board_list = [
                {
                    "id": str(r[0]),
                    "organizationId": str(r[1]),
                    "tenantId": str(r[2]),
                    "name": r[3],
                    "createdAt": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "updatedAt": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
                }
                for r in items
            ]
            return board_list, next_cursor

    return with_tenant(tenant_id, _list)


def get_board_snapshot(tenant_id: str, board_id: str) -> dict[str, Any]:
    def _snapshot(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, organization_id, tenant_id, name, created_at, updated_at
                FROM boards
                WHERE id = %s AND tenant_id = %s;
                """,
                (board_id, tenant_id),
            )
            b_row = cur.fetchone()
            if not b_row:
                raise not_found("Board not found")

            board = {
                "id": str(b_row[0]),
                "organizationId": str(b_row[1]),
                "tenantId": str(b_row[2]),
                "name": b_row[3],
                "createdAt": b_row[4].isoformat()
                if hasattr(b_row[4], "isoformat")
                else str(b_row[4]),
                "updatedAt": b_row[5].isoformat()
                if hasattr(b_row[5], "isoformat")
                else str(b_row[5]),
            }

            cur.execute(
                """
                SELECT id, tenant_id, board_id, key, name, position, created_at
                FROM columns
                WHERE board_id = %s AND tenant_id = %s
                ORDER BY position ASC;
                """,
                (board_id, tenant_id),
            )
            columns = [
                {
                    "id": str(c[0]),
                    "tenantId": str(c[1]),
                    "boardId": str(c[2]),
                    "key": c[3],
                    "name": c[4],
                    "position": c[5],
                    "createdAt": c[6].isoformat() if hasattr(c[6], "isoformat") else str(c[6]),
                }
                for c in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT id, column_id, title, description, assignee_id, priority, position, version, created_at, updated_at
                FROM tasks
                WHERE board_id = %s AND tenant_id = %s
                ORDER BY column_id, position COLLATE "C", id;
                """,
                (board_id, tenant_id),
            )
            tasks = [
                {
                    "id": str(t[0]),
                    "columnId": str(t[1]),
                    "title": t[2],
                    "description": t[3],
                    "assigneeId": str(t[4]) if t[4] else None,
                    "priority": t[5],
                    "position": t[6],
                    "version": t[7],
                    "createdAt": t[8].isoformat() if hasattr(t[8], "isoformat") else str(t[8]),
                    "updatedAt": t[9].isoformat() if hasattr(t[9], "isoformat") else str(t[9]),
                }
                for t in cur.fetchall()
            ]

            return {
                "board": board,
                "columns": columns,
                "tasks": tasks,
            }

    return with_tenant(tenant_id, _snapshot)


def update_board(
    org_id: str, tenant_id: str, user_id: str, board_id: str, name: str
) -> dict[str, Any]:
    def _update(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name FROM boards
                WHERE id = %s AND tenant_id = %s;
                """,
                (board_id, tenant_id),
            )
            old = cur.fetchone()
            if not old:
                raise not_found("Board not found")
            old_name = old[0]

            cur.execute(
                """
                UPDATE boards
                SET name = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, organization_id, tenant_id, name, created_at, updated_at;
                """,
                (name, board_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Board not found")

            board = {
                "id": str(row[0]),
                "organizationId": str(row[1]),
                "tenantId": str(row[2]),
                "name": row[3],
                "createdAt": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                "updatedAt": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            }

            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action="board.updated",
                board_id=board_id,
                before={"name": old_name},
                after={"name": name},
            )
            return board

    return with_tenant(tenant_id, _update)


def delete_board(org_id: str, tenant_id: str, user_id: str, board_id: str) -> None:
    def _delete(conn: Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name FROM boards
                WHERE id = %s AND tenant_id = %s;
                """,
                (board_id, tenant_id),
            )
            old = cur.fetchone()
            if not old:
                raise not_found("Board not found")
            old_name = old[0]

            cur.execute(
                "DELETE FROM boards WHERE id = %s AND tenant_id = %s;",
                (board_id, tenant_id),
            )

            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action="board.deleted",
                board_id=board_id,
                before={"name": old_name},
            )

    with_tenant(tenant_id, _delete)
