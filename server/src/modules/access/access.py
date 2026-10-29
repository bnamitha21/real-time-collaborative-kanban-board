from dataclasses import dataclass
from typing import Literal

from psycopg import Connection

from server.src.db.pool import with_tx

Role = Literal["org_admin", "tenant_admin", "member"]

@dataclass
class TenantAccess:
    organization_id: str
    tenant_id: str
    role: Role

def resolve_tenant_access(
    user_id: str,
    tenant_id: str,
    conn: Connection | None = None,
) -> TenantAccess | None:
    """Highest-privilege access the user holds for this tenant, or None. Never throws for 'no access'."""
    def _query(c: Connection) -> TenantAccess | None:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT t.organization_id AS "organization_id", t.id AS "tenant_id", m.role
                FROM tenants t
                JOIN memberships m
                  ON m.user_id = %s
                 AND m.organization_id = t.organization_id
                 AND (m.tenant_id = t.id OR m.role = 'org_admin')
                WHERE t.id = %s
                ORDER BY (m.role = 'org_admin') DESC, (m.role = 'tenant_admin') DESC
                LIMIT 1;
                """,
                (user_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return TenantAccess(
                organization_id=str(row[0]),
                tenant_id=str(row[1]),
                role=row[2],
            )

    if conn is not None:
        return _query(conn)
    return with_tx(_query)

def resolve_org_role(
    user_id: str,
    org_id: str,
    conn: Connection | None = None,
) -> Literal["org_admin", "member_of_org"] | None:
    """org_admin row -> 'org_admin'; any membership in org -> 'member_of_org'; else None."""
    def _query(c: Connection) -> Literal["org_admin", "member_of_org"] | None:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT role FROM memberships
                WHERE user_id = %s AND organization_id = %s
                ORDER BY (role = 'org_admin') DESC
                LIMIT 1;
                """,
                (user_id, org_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            if row[0] == "org_admin":
                return "org_admin"
            return "member_of_org"

    if conn is not None:
        return _query(conn)
    return with_tx(_query)
