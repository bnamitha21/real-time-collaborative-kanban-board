from flask import Blueprint, g, jsonify
from server.src.middleware.authenticate import authenticate
from server.src.middleware.tenant_access import require_tenant_access
from server.src.middleware.validate import validate_request
from server.src.modules.boards.schemas import (
    CreateBoardSchema,
    ListBoardsQuerySchema,
    UpdateBoardSchema,
)
from server.src.modules.boards.service import (
    create_board,
    delete_board,
    get_board_snapshot,
    list_boards,
    update_board,
)

boards_bp = Blueprint("boards", __name__, url_prefix="/api/v1")


@boards_bp.post("/tenants/<tenant_id>/boards")
@authenticate
@validate_request(body_model=CreateBoardSchema)
@require_tenant_access("board.create")
def handle_create_board(tenant_id: str):
    body: CreateBoardSchema = g.validated_body
    board = create_board(
        org_id=g.access.organization_id,
        tenant_id=tenant_id,
        user_id=g.user_id,
        name=body.name,
    )
    return jsonify({"data": board}), 201


@boards_bp.get("/tenants/<tenant_id>/boards")
@authenticate
@validate_request(query_model=ListBoardsQuerySchema)
@require_tenant_access("board.read")
def handle_list_boards(tenant_id: str):
    query: ListBoardsQuerySchema = getattr(g, "validated_query", ListBoardsQuerySchema())
    limit = query.limit if query.limit is not None else 50
    boards, next_cursor = list_boards(
        tenant_id=tenant_id,
        limit=limit,
        cursor=query.cursor,
    )
    return jsonify({"data": boards, "nextCursor": next_cursor}), 200


@boards_bp.get("/boards/<board_id>")
@authenticate
@validate_request()
@require_tenant_access("board.read")
def handle_get_board_snapshot(board_id: str):
    snapshot = get_board_snapshot(
        tenant_id=g.tenant_id,
        board_id=board_id,
    )
    return jsonify({"data": snapshot}), 200


@boards_bp.patch("/boards/<board_id>")
@authenticate
@validate_request(body_model=UpdateBoardSchema)
@require_tenant_access("board.update")
def handle_update_board(board_id: str):
    body: UpdateBoardSchema = g.validated_body
    board = update_board(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        board_id=board_id,
        name=body.name,
    )
    return jsonify({"data": board}), 200


@boards_bp.delete("/boards/<board_id>")
@authenticate
@validate_request()
@require_tenant_access("board.delete")
def handle_delete_board(board_id: str):
    delete_board(
        org_id=g.access.organization_id,
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        board_id=board_id,
    )
    return jsonify({"data": {"success": True}}), 200
