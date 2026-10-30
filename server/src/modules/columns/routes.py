from flask import Blueprint, g, jsonify
from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_tenant_access
from server.src.middleware.validate import validate_request
from server.src.modules.columns.schemas import UpdateColumnSchema
from server.src.modules.columns.service import list_board_columns, update_column

columns_bp = Blueprint("columns", __name__, url_prefix="/api/v1")


@columns_bp.get("/boards/<board_id>/columns")
@columns_bp.get("/tenants/<tenant_id>/boards/<board_id>/columns")
@authenticate
@validate_request()
@require_tenant_access("column.read")
def handle_list_columns(board_id: str, tenant_id: str | None = None):
    columns = list_board_columns(
        tenant_id=g.tenant_id,
        board_id=board_id,
    )
    return jsonify({"data": columns}), 200


@columns_bp.patch("/columns/<column_id>")
@authenticate
@validate_request(body_model=UpdateColumnSchema)
@require_tenant_access("column.update")
def handle_update_column(column_id: str):
    body: UpdateColumnSchema = g.validated_body
    column = update_column(
        tenant_id=g.tenant_id,
        column_id=column_id,
        name=body.name,
    )
    return jsonify({"data": column}), 200
