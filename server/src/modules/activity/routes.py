from flask import Blueprint, g, jsonify

from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_tenant_access
from server.src.middleware.validate import validate_request
from server.src.modules.activity.schemas import ActivityQuerySchema
from server.src.modules.activity.service import list_tenant_activity

activity_bp = Blueprint("activity", __name__, url_prefix="/api/v1")


@activity_bp.get("/tenants/<tenant_id>/activity")
@authenticate
@validate_request(query_model=ActivityQuerySchema)
@require_tenant_access("activity.read")
def handle_list_activity(tenant_id: str):
    query: ActivityQuerySchema = getattr(g, "validated_query", ActivityQuerySchema())
    limit = query.limit if query.limit is not None else 50
    activities, next_cursor = list_tenant_activity(
        tenant_id=tenant_id,
        board_id=query.boardId,
        task_id=query.taskId,
        cursor=query.cursor,
        limit=limit,
    )
    return jsonify({"data": activities, "nextCursor": next_cursor}), 200

