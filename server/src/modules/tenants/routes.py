from flask import Blueprint, g, jsonify
from psycopg import Connection
from server.src.db.pool import with_tx
from server.src.lib.errors import forbidden
from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_tenant_access
from server.src.middleware.validate import validate_request
from server.src.modules.tenants.schemas import AddMemberSchema, UpdateTenantSchema
from server.src.modules.tenants.service import (
    add_tenant_member,
    delete_tenant,
    get_tenant,
    remove_tenant_member,
    update_tenant,
)

tenants_bp = Blueprint("tenants", __name__, url_prefix="/api/v1/tenants")


@tenants_bp.get("/<tenant_id>")
@authenticate
@validate_request()
@require_tenant_access("tenant.read")
def handle_get_tenant(tenant_id: str):
    tenant = get_tenant(tenant_id)
    return jsonify({"data": tenant}), 200


@tenants_bp.patch("/<tenant_id>")
@authenticate
@validate_request(body_model=UpdateTenantSchema)
@require_tenant_access("tenant.update")
def handle_update_tenant(tenant_id: str):
    body: UpdateTenantSchema = g.validated_body
    tenant = update_tenant(tenant_id, body.name)
    return jsonify({"data": tenant}), 200


@tenants_bp.delete("/<tenant_id>")
@authenticate
@validate_request()
@require_tenant_access("tenant.delete")
def handle_delete_tenant(tenant_id: str):
    delete_tenant(tenant_id)
    return jsonify({"data": {"success": True}}), 200


@tenants_bp.post("/<tenant_id>/members")
@authenticate
@validate_request(body_model=AddMemberSchema)
@require_tenant_access("tenant.read")
def handle_add_member(tenant_id: str):
    caller_role = g.access.role
    if caller_role == "member":
        raise forbidden("Members cannot manage branch members")

    body: AddMemberSchema = g.validated_body
    if caller_role == "tenant_admin" and body.role == "tenant_admin":
        raise forbidden("Tenant admins cannot assign tenant admin role")

    member = add_tenant_member(
        org_id=g.access.organization_id,
        tenant_id=tenant_id,
        email=body.email,
        role=body.role,
    )
    return jsonify({"data": member}), 201


@tenants_bp.delete("/<tenant_id>/members/<user_id>")
@authenticate
@validate_request()
@require_tenant_access("tenant.read")
def handle_remove_member(tenant_id: str, user_id: str):
    caller_role = g.access.role
    if caller_role == "member":
        raise forbidden("Members cannot manage branch members")

    if caller_role == "tenant_admin":
        # Check target user's role in this tenant
        def _check_target(conn: Connection) -> str | None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role FROM memberships WHERE user_id = %s AND tenant_id = %s;",
                    (user_id, tenant_id),
                )
                row = cur.fetchone()
                return row[0] if row else None

        target_role = with_tx(_check_target)
        if target_role in ("tenant_admin", "org_admin"):
            raise forbidden("Tenant admins cannot remove other administrators")

    remove_tenant_member(tenant_id, user_id)
    return jsonify({"data": {"success": True}}), 200
