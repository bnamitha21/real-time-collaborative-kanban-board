from flask import Blueprint, g, jsonify
from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_org_access
from server.src.middleware.validate import validate_request
from server.src.modules.organizations.schemas import CreateOrgSchema, UpdateOrgSchema
from server.src.modules.organizations.service import (
    create_organization,
    delete_organization,
    get_organization,
    list_user_organizations,
    update_organization,
)
from server.src.modules.tenants.schemas import CreateTenantSchema
from server.src.modules.tenants.service import create_tenant, list_tenants

organizations_bp = Blueprint("organizations", __name__, url_prefix="/api/v1/organizations")


@organizations_bp.post("")
@authenticate
@validate_request(body_model=CreateOrgSchema)
def handle_create_org():
    body: CreateOrgSchema = g.validated_body
    org = create_organization(g.user_id, body.name)
    return jsonify({"data": org}), 201


@organizations_bp.get("")
@authenticate
def handle_list_orgs():
    orgs = list_user_organizations(g.user_id)
    return jsonify({"data": orgs}), 200


@organizations_bp.get("/<org_id>")
@authenticate
@validate_request()
@require_org_access("org.read")
def handle_get_org(org_id: str):
    org = get_organization(org_id)
    return jsonify({"data": org}), 200


@organizations_bp.patch("/<org_id>")
@authenticate
@validate_request(body_model=UpdateOrgSchema)
@require_org_access("org.update")
def handle_update_org(org_id: str):
    body: UpdateOrgSchema = g.validated_body
    org = update_organization(org_id, body.name)
    return jsonify({"data": org}), 200


@organizations_bp.delete("/<org_id>")
@authenticate
@validate_request()
@require_org_access("org.delete")
def handle_delete_org(org_id: str):
    delete_organization(org_id)
    return jsonify({"data": {"success": True}}), 200


@organizations_bp.post("/<org_id>/tenants")
@authenticate
@validate_request(body_model=CreateTenantSchema)
@require_org_access("tenant.create")
def handle_create_tenant(org_id: str):
    body: CreateTenantSchema = g.validated_body
    tenant = create_tenant(org_id, body.name)
    return jsonify({"data": tenant}), 201


@organizations_bp.get("/<org_id>/tenants")
@authenticate
@validate_request()
@require_org_access("org.read")
def handle_list_tenants(org_id: str):
    is_admin = g.org_role == "org_admin"
    tenants = list_tenants(g.user_id, org_id, is_admin)
    return jsonify({"data": tenants}), 200
