import time
import uuid
from typing import Any

import jwt
from flask import Flask, request, session
from flask_socketio import ConnectionRefusedError, SocketIO, join_room, leave_room  # type: ignore[import-untyped]

from server.src.config.env import env
from server.src.middleware.tenant_access import load_board_scope
from server.src.modules.access.access import resolve_tenant_access
from server.src.realtime.presence import (
    get_socket_boards,
    join_board,
    join_tenant,
    leave_all,
    leave_board,
)
from server.src.realtime.publisher import set_socketio

socketio = SocketIO(
    cors_allowed_origins="*" if env.FLASK_ENV == "development" else [env.CLIENT_ORIGIN],
    max_http_buffer_size=100_000,
    ping_timeout=8,
    ping_interval=10,
    manage_session=False,
    message_queue=env.REDIS_URL if env.REDIS_URL else None,
)


_socket_sessions: dict[str, dict[str, Any]] = {}


def extract_token(auth: Any) -> str | None:
    if isinstance(auth, dict) and auth.get("token"):
        return str(auth["token"])
    if request.args.get("token"):
        return str(request.args.get("token"))
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


@socketio.on("connect")
def handle_connect(auth: Any = None) -> None:
    token = extract_token(auth)
    if not token:
        raise ConnectionRefusedError("UNAUTHENTICATED")

    try:
        payload = jwt.decode(token, env.JWT_ACCESS_SECRET, algorithms=["HS256"])
        user_id = str(payload["sub"])
        exp = payload.get("exp")
        if exp and exp < time.time():
            raise ConnectionRefusedError("UNAUTHENTICATED")

        sid = str(getattr(request, "sid", ""))
        _socket_sessions[sid] = {"user_id": user_id, "exp": exp}
        try:
            session["user_id"] = user_id
            session["exp"] = exp
        except RuntimeError:
            pass
        join_room(f"user:{user_id}")

    except (jwt.PyJWTError, KeyError, ValueError):
        raise ConnectionRefusedError("UNAUTHENTICATED") from None


def get_current_user_id() -> str | None:
    sid = str(getattr(request, "sid", ""))
    info = _socket_sessions.get(sid)
    if info:
        return info.get("user_id")
    try:
        return session.get("user_id")
    except RuntimeError:
        return None


@socketio.on("disconnect")
def handle_disconnect() -> None:
    sid = str(getattr(request, "sid", ""))
    user_id = get_current_user_id()
    _socket_sessions.pop(sid, None)
    if not user_id:
        return

    affected_tenants = leave_all(sid, user_id)
    for tenant_id, presence_list in affected_tenants:
        socketio.emit(
            "presence:update",
            {"tenantId": tenant_id, "users": presence_list},
            room=f"tenant:{tenant_id}",
        )


@socketio.on("board:subscribe")
def handle_board_subscribe(data: Any) -> dict[str, Any]:
    user_id = get_current_user_id()
    if not user_id:
        return {"ok": False, "code": "UNAUTHENTICATED"}

    board_id = data.get("boardId") if isinstance(data, dict) else None
    if not board_id:
        return {"ok": False, "code": "VALIDATION_ERROR"}

    try:
        uuid.UUID(str(board_id))
    except (ValueError, TypeError):
        return {"ok": False, "code": "VALIDATION_ERROR"}

    scope = load_board_scope(board_id)
    if not scope:
        return {"ok": False, "code": "NOT_FOUND"}

    tenant_id, _org_id = scope
    access = resolve_tenant_access(user_id, tenant_id)
    if not access:
        return {"ok": False, "code": "NOT_FOUND"}

    sid = str(getattr(request, "sid", ""))
    # Leave any previous boards
    for prev_board in get_socket_boards(sid):
        leave_room(f"tenant:{tenant_id}:board:{prev_board}")
        leave_board(prev_board, sid)

    join_room(f"tenant:{tenant_id}")
    join_room(f"tenant:{tenant_id}:board:{board_id}")
    join_board(board_id, sid)

    presence_users = join_tenant(tenant_id, user_id, sid)
    socketio.emit(
        "presence:update",
        {"tenantId": tenant_id, "users": presence_users},
        room=f"tenant:{tenant_id}",
    )

    return {"ok": True, "presence": presence_users}


@socketio.on("board:unsubscribe")
def handle_board_unsubscribe(data: Any) -> dict[str, Any]:
    user_id = get_current_user_id()
    if not user_id:
        return {"ok": False, "code": "UNAUTHENTICATED"}

    board_id = data.get("boardId") if isinstance(data, dict) else None
    if not board_id:
        return {"ok": True}

    scope = load_board_scope(board_id)
    if scope:
        tenant_id, _ = scope
        sid = str(getattr(request, "sid", ""))
        leave_room(f"tenant:{tenant_id}:board:{board_id}")
        leave_board(board_id, sid)

    return {"ok": True}


def init_realtime(app: Flask) -> SocketIO:
    socketio.init_app(app)
    set_socketio(socketio)
    return socketio
