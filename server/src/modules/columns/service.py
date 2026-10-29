from typing import Any

from psycopg import Connection
from server.src.db.pool import with_tenant
from server.src.lib.errors import not_found


def list_board_columns(tenant_id: str, board_id: str) -> list[dict[str, Any]]:
    def _list(conn: Connection) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, board_id, key, name, position, created_at
                FROM columns
                WHERE board_id = %s AND tenant_id = %s
                ORDER BY position ASC;
                """,
                (board_id, tenant_id),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "tenantId": str(r[1]),
                    "boardId": str(r[2]),
                    "key": r[3],
                    "name": r[4],
                    "position": r[5],
                    "createdAt": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                }
                for r in rows
            ]

    return with_tenant(tenant_id, _list)


def update_column(tenant_id: str, column_id: str, name: str) -> dict[str, Any]:
    def _update(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE columns
                SET name = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, board_id, key, name, position, created_at;
                """,
                (name, column_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Column not found")
            return {
                "id": str(row[0]),
                "tenantId": str(row[1]),
                "boardId": str(row[2]),
                "key": row[3],
                "name": row[4],
                "position": row[5],
                "createdAt": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
            }

    return with_tenant(tenant_id, _update)
