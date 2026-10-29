from typing import Any

_socketio_instance: Any = None


def set_socketio(sio: Any) -> None:
    global _socketio_instance
    _socketio_instance = sio


def get_socketio() -> Any:
    return _socketio_instance


def publish_to_board(tenant_id: str, board_id: str, event: str, payload: dict[str, Any]) -> None:
    sio = get_socketio()
    if sio is not None:
        room = f"tenant:{tenant_id}:board:{board_id}"
        sio.emit(event, payload, room=room)


def publish_to_tenant(tenant_id: str, event: str, payload: dict[str, Any]) -> None:
    sio = get_socketio()
    if sio is not None:
        room = f"tenant:{tenant_id}"
        sio.emit(event, payload, room=room)


def publish_to_user(user_id: str, event: str, payload: dict[str, Any]) -> None:
    sio = get_socketio()
    if sio is not None:
        room = f"user:{user_id}"
        sio.emit(event, payload, room=room)

