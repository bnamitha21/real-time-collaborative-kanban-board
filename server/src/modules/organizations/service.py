from typing import Any

from psycopg import Connection
from server.src.db.pool import with_tx
from server.src.lib.errors import bad_request, not_found


def create_organization(user_id: str, name: str) -> dict[str, Any]:
    def _create(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO organizations (name)
                VALUES (%s)
                RETURNING id, name, created_at, updated_at;
                """,
                (name,),
            )
            row = cur.fetchone()
            if not row:
                raise bad_request("Failed to create organization")
            org = {
                "id": str(row[0]),
                "name": row[1],
                "createdAt": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                "updatedAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
            }

            # Creator becomes org_admin
            cur.execute(
                """
                INSERT INTO memberships (user_id, organization_id, role)
                VALUES (%s, %s, 'org_admin');
                """,
                (user_id, org["id"]),
            )
            return org

    return with_tx(_create)


def list_user_organizations(user_id: str) -> list[dict[str, Any]]:
    def _list(conn: Connection) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT o.id, o.name, o.created_at, o.updated_at
                FROM organizations o
                JOIN memberships m ON m.organization_id = o.id
                WHERE m.user_id = %s
                ORDER BY o.name ASC;
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "name": r[1],
                    "createdAt": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                    "updatedAt": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                }
                for r in rows
            ]

    return with_tx(_list)


def get_organization(org_id: str) -> dict[str, Any]:
    def _get(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, created_at, updated_at
                FROM organizations
                WHERE id = %s;
                """,
                (org_id,),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Organization not found")
            return {
                "id": str(row[0]),
                "name": row[1],
                "createdAt": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                "updatedAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
            }

    return with_tx(_get)


def update_organization(org_id: str, name: str) -> dict[str, Any]:
    def _update(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE organizations
                SET name = %s
                WHERE id = %s
                RETURNING id, name, created_at, updated_at;
                """,
                (name, org_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Organization not found")
            return {
                "id": str(row[0]),
                "name": row[1],
                "createdAt": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                "updatedAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
            }

    return with_tx(_update)


def delete_organization(org_id: str) -> None:
    def _delete(conn: Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM organizations
                WHERE id = %s;
                """,
                (org_id,),
            )
            if cur.rowcount == 0:
                raise not_found("Organization not found")

    with_tx(_delete)
