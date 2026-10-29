from flask import Blueprint, g, jsonify
from psycopg import Connection

from server.src.db.pool import with_tx
from server.src.middleware.authenticate import authenticate

workspaces_bp = Blueprint("workspaces", __name__, url_prefix="/api/v1/me")

@workspaces_bp.get("/workspaces")
@authenticate
def get_workspaces():
    user_id = g.user_id

    def _query(conn: Connection):
        with conn.cursor() as cur:
            # 1. Fetch all distinct organizations where user has any membership
            cur.execute(
                """
                SELECT DISTINCT o.id, o.name
                FROM organizations o
                JOIN memberships m ON m.organization_id = o.id
                WHERE m.user_id = %s
                ORDER BY o.name;
                """,
                (user_id,),
            )
            orgs = cur.fetchall()

            result = []
            for org_id, org_name in orgs:
                # Check user's org-level role
                cur.execute(
                    """
                    SELECT role FROM memberships
                    WHERE user_id = %s AND organization_id = %s AND role = 'org_admin'
                    LIMIT 1;
                    """,
                    (user_id, org_id),
                )
                is_org_admin = cur.fetchone() is not None

                if is_org_admin:
                    # Org admin sees all tenants in this organization
                    cur.execute(
                        """
                        SELECT id, name FROM tenants
                        WHERE organization_id = %s
                        ORDER BY name;
                        """,
                        (org_id,),
                    )
                    tenants = [
                        {"id": str(t[0]), "name": str(t[1]), "role": "org_admin"}
                        for t in cur.fetchall()
                    ]
                    org_role = "org_admin"
                else:
                    # Tenant admin / member sees only their branch memberships
                    cur.execute(
                        """
                        SELECT t.id, t.name, m.role
                        FROM memberships m
                        JOIN tenants t ON t.id = m.tenant_id
                        WHERE m.user_id = %s AND m.organization_id = %s
                        ORDER BY t.name;
                        """,
                        (user_id, org_id),
                    )
                    tenants = [
                        {"id": str(t[0]), "name": str(t[1]), "role": str(t[2])}
                        for t in cur.fetchall()
                    ]
                    org_role = "member"

                result.append({
                    "organization": {"id": str(org_id), "name": str(org_name)},
                    "role": org_role,
                    "tenants": tenants,
                })

            return result

    data = with_tx(_query)
    return jsonify({"data": data}), 200
