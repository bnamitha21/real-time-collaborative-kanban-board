from flask import Blueprint, g, jsonify, request
from server.src.lib.errors import bad_request
from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_tenant_access
from server.src.middleware.validate import validate_request
from server.src.modules.tasks.schemas import CreateTaskSchema, UpdateTaskSchema
from server.src.modules.tasks.service import (
    create_task,
    delete_task,
    get_task,
    update_task,
)

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/v1")


@tasks_bp.post("/boards/<board_id>/tasks")
@authenticate
@validate_request(body_model=CreateTaskSchema)
@require_tenant_access("task.create")
def handle_create_task(board_id: str):
    body: CreateTaskSchema = g.validated_body
    task, _replayed = create_task(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        board_id=board_id,
        column_id=body.columnId,
        title=body.title,
        description=body.description or "",
        assignee_id=body.assigneeId,
        priority=body.priority or "medium",
        action_id=body.actionId,
    )
    return jsonify({"data": task}), 201


@tasks_bp.get("/tasks/<task_id>")
@authenticate
@validate_request()
@require_tenant_access("task.read")
def handle_get_task(task_id: str):
    task = get_task(
        tenant_id=g.tenant_id,
        task_id=task_id,
    )
    return jsonify({"data": task}), 200


@tasks_bp.patch("/tasks/<task_id>")
@authenticate
@validate_request(body_model=UpdateTaskSchema)
@require_tenant_access("task.update")
def handle_update_task(task_id: str):
    body: UpdateTaskSchema = g.validated_body
    assignee_provided = "assigneeId" in body.model_fields_set

    task, _replayed = update_task(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        caller_role=g.access.role,
        task_id=task_id,
        expected_version=body.expectedVersion,
        action_id=body.actionId,
        title=body.title,
        description=body.description,
        assignee_id=body.assigneeId,
        assignee_provided=assignee_provided,
        priority=body.priority,
    )
    return jsonify({"data": task}), 200


@tasks_bp.delete("/tasks/<task_id>")
@authenticate
@validate_request()
@require_tenant_access("task.delete")
def handle_delete_task(task_id: str):
    expected_version_raw = request.args.get("expectedVersion")
    action_id = request.args.get("actionId")

    if not expected_version_raw and request.is_json:
        json_body = request.get_json(silent=True) or {}
        expected_version_raw = json_body.get("expectedVersion")
        action_id = action_id or json_body.get("actionId")

    if expected_version_raw is None:
        raise bad_request("expectedVersion is required")
    try:
        expected_version = int(expected_version_raw)
    except (ValueError, TypeError):
        raise bad_request("expectedVersion must be an integer")

    delete_task(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        caller_role=g.access.role,
        task_id=task_id,
        expected_version=expected_version,
        action_id=action_id,
    )
    return jsonify({"data": {"success": True}}), 200
