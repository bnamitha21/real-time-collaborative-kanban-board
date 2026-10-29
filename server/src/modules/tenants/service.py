from typing import Any

from psycopg import Connection
from server.src.db.pool import with_tx
from server.src.lib.errors import bad_request, not_found


def create_tenant(org_id: str, name: str) -> dict[str, Any]:
    def _create(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM tenants WHERE organization_id = %s AND name = %s;",
                (org_id, name),
            )
            if cur.fetchone():
                raise bad_request("A branch with this name already exists in this organization")

            cur.execute(
                """
                INSERT INTO tenants (organization_id, name)
                VALUES (%s, %s)
                RETURNING id, organization_id, name, created_at, updated_at;
                """,
                (org_id, name),
            )
            row = cur.fetchone()
            if not row:
                raise bad_request("Failed to create tenant")
            return {
                "id": str(row[0]),
                "organizationId": str(row[1]),
                "name": row[2],
                "createdAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                "updatedAt": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
            }

    return with_tx(_create)


def list_tenants(user_id: str, org_id: str, is_org_admin: bool) -> list[dict[str, Any]]:
    def _list(conn: Connection) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            if is_org_admin:
                cur.execute(
                    """
                    SELECT id, organization_id, name, created_at, updated_at
                    FROM tenants
                    WHERE organization_id = %s
                    ORDER BY name ASC;
                    """,
                    (org_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT t.id, t.organization_id, t.name, t.created_at, t.updated_at
                    FROM tenants t
                    JOIN memberships m ON m.tenant_id = t.id
                    WHERE t.organization_id = %s AND m.user_id = %s
                    ORDER BY t.name ASC;
                    """,
                    (org_id, user_id),
                )
            rows = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "organizationId": str(r[1]),
                    "name": r[2],
                    "createdAt": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                    "updatedAt": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                }
                for r in rows
            ]

    return with_tx(_list)


def get_tenant(tenant_id: str) -> dict[str, Any]:
    def _get(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, organization_id, name, created_at, updated_at
                FROM tenants
                WHERE id = %s;
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Tenant not found")
            return {
                "id": str(row[0]),
                "organizationId": str(row[1]),
                "name": row[2],
                "createdAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                "updatedAt": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
            }

    return with_tx(_get)


def update_tenant(tenant_id: str, name: str) -> dict[str, Any]:
    def _update(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute("SELECT organization_id FROM tenants WHERE id = %s;", (tenant_id,))
            org_row = cur.fetchone()
            if not org_row:
                raise not_found("Tenant not found")
            org_id = org_row[0]

            cur.execute(
                "SELECT 1 FROM tenants WHERE organization_id = %s AND name = %s AND id <> %s;",
                (org_id, name, tenant_id),
            )
            if cur.fetchone():
                raise bad_request("A branch with this name already exists in this organization")

            cur.execute(
                """
                UPDATE tenants
                SET name = %s
                WHERE id = %s
                RETURNING id, organization_id, name, created_at, updated_at;
                """,
                (name, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Tenant not found")
            return {
                "id": str(row[0]),
                "organizationId": str(row[1]),
                "name": row[2],
                "createdAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                "updatedAt": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
            }

    return with_tx(_update)


def delete_tenant(tenant_id: str) -> None:
    def _delete(conn: Connection) -> None:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s;", (tenant_id,))
            if cur.rowcount == 0:
                raise not_found("Tenant not found")

    with_tx(_delete)


def add_tenant_member(org_id: str, tenant_id: str, email: str, role: str) -> dict[str, Any]:
    def _add(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE lower(email) = lower(%s);", (email,))
            user_row = cur.fetchone()
            if not user_row:
                raise not_found("User with specified email not found")
            target_user_id = str(user_row[0])

            cur.execute(
                "SELECT 1 FROM memberships WHERE user_id = %s AND tenant_id = %s;",
                (target_user_id, tenant_id),
            )
            if cur.fetchone():
                raise bad_request("User is already a member of this branch")

            cur.execute(
                """
                INSERT INTO memberships (user_id, organization_id, tenant_id, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, organization_id, tenant_id, role, created_at;
                """,
                (target_user_id, org_id, tenant_id, role),
            )
            row = cur.fetchone()
            if not row:
                raise bad_request("Failed to add branch member")
            return {
                "id": str(row[0]),
                "userId": str(row[1]),
                "organizationId": str(row[2]),
                "tenantId": str(row[3]),
                "role": row[4],
                "createdAt": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            }

    return with_tx(_add)


def remove_tenant_member(tenant_id: str, target_user_id: str) -> None:
    def _remove(conn: Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM memberships WHERE user_id = %s AND tenant_id = %s;",
                (target_user_id, tenant_id),
            )
            if cur.rowcount == 0:
                raise not_found("Membership not found")

    with_tx(_remove)
