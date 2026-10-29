from flask import Blueprint, g, jsonify, request
from server.src.lib.errors import bad_request
from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_tenant_access
from server.src.middleware.validate import validate_request
from server.src.modules.tasks.schemas import (
    CreateTaskSchema,
    MoveTaskSchema,
    UpdateTaskSchema,
)
from server.src.modules.tasks.service import (
    create_task,
    delete_task,
    get_task,
    move_task,
    update_task,
)
from server.src.realtime.publisher import publish_to_board

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/v1")


@tasks_bp.post("/boards/<board_id>/tasks")
@authenticate
@validate_request(body_model=CreateTaskSchema)
@require_tenant_access("task.create")
def handle_create_task(board_id: str):
    body: CreateTaskSchema = g.validated_body
    task, replayed = create_task(
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

    if not replayed:
        publish_to_board(
            g.tenant_id,
            board_id,
            "task:created",
            {
                "task": task,
                "actorId": g.user_id,
                "actionId": body.actionId,
            },
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

    task, replayed = update_task(
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

    if not replayed:
        publish_to_board(
            g.tenant_id,
            task["boardId"],
            "task:updated",
            {
                "task": task,
                "actorId": g.user_id,
                "actionId": body.actionId,
            },
        )

    return jsonify({"data": task}), 200


@tasks_bp.post("/tasks/<task_id>/move")
@authenticate
@validate_request(body_model=MoveTaskSchema)
@require_tenant_access("task.move")
def handle_move_task(task_id: str):
    body: MoveTaskSchema = g.validated_body
    task, replayed, event_type, rebalanced, from_column_id = move_task(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        caller_role=g.access.role,
        task_id=task_id,
        expected_version=body.expectedVersion,
        to_column_id=body.toColumnId,
        after_task_id=body.afterTaskId,
        action_id=body.actionId,
    )

    if not replayed:
        publish_to_board(
            g.tenant_id,
            task["boardId"],
            event_type,
            {
                "task": task,
                "fromColumnId": from_column_id,
                "actorId": g.user_id,
                "actionId": body.actionId,
            },
        )
        if rebalanced:
            publish_to_board(
                g.tenant_id,
                task["boardId"],
                "board:resync",
                {"boardId": task["boardId"]},
            )

    return jsonify({"data": {"task": task}}), 200


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

    replayed = delete_task(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        caller_role=g.access.role,
        task_id=task_id,
        expected_version=expected_version,
        action_id=action_id,
    )

    if not replayed:
        publish_to_board(
            g.tenant_id,
            g.access.tenant_id,
            "task:deleted",
            {
                "taskId": task_id,
                "version": expected_version,
                "actorId": g.user_id,
                "actionId": action_id,
            },
        )

    return jsonify({"data": {"success": True}}), 200
