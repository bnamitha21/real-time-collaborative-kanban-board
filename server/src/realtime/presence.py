from typing import Any

from psycopg import Connection

from server.src.db.pool import with_tx

# Maps: tenant_id -> user_id -> set of socket_ids
_tenant_presence: dict[str, dict[str, set[str]]] = {}
# Maps: socket_id -> set of tenant_ids
_socket_tenants: dict[str, set[str]] = {}
# Maps: socket_id -> set of board_ids
_socket_boards: dict[str, set[str]] = {}


def get_tenant_members(tenant_id: str) -> list[dict[str, str]]:
    def _query(conn: Connection) -> list[dict[str, str]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT u.id, u.name
                FROM users u
                JOIN memberships m ON m.user_id = u.id
                WHERE m.tenant_id = %s
                   OR (m.organization_id = (SELECT organization_id FROM tenants WHERE id = %s) AND m.role = 'org_admin');
                """,
                (tenant_id, tenant_id),
            )
            return [{"id": str(r[0]), "name": r[1]} for r in cur.fetchall()]

    return with_tx(_query)


def get_presence_list(tenant_id: str) -> list[dict[str, Any]]:
    members = get_tenant_members(tenant_id)
    online_map = _tenant_presence.get(tenant_id, {})
    return [
        {
            "userId": m["id"],
            "name": m["name"],
            "online": bool(online_map.get(m["id"])),
        }
        for m in members
    ]


def join_tenant(tenant_id: str, user_id: str, sid: str) -> list[dict[str, Any]]:
    if tenant_id not in _tenant_presence:
        _tenant_presence[tenant_id] = {}
    if user_id not in _tenant_presence[tenant_id]:
        _tenant_presence[tenant_id][user_id] = set()

    _tenant_presence[tenant_id][user_id].add(sid)

    if sid not in _socket_tenants:
        _socket_tenants[sid] = set()
    _socket_tenants[sid].add(tenant_id)

    return get_presence_list(tenant_id)


def leave_tenant(tenant_id: str, user_id: str, sid: str) -> list[dict[str, Any]]:
    if tenant_id in _tenant_presence and user_id in _tenant_presence[tenant_id]:
        _tenant_presence[tenant_id][user_id].discard(sid)
        if not _tenant_presence[tenant_id][user_id]:
            _tenant_presence[tenant_id].pop(user_id, None)

    if sid in _socket_tenants:
        _socket_tenants[sid].discard(tenant_id)
        if not _socket_tenants[sid]:
            _socket_tenants.pop(sid, None)

    return get_presence_list(tenant_id)


def leave_all(sid: str, user_id: str) -> list[tuple[str, list[dict[str, Any]]]]:
    tenants = list(_socket_tenants.get(sid, set()))
    results = []
    for t_id in tenants:
        presence = leave_tenant(t_id, user_id, sid)
        results.append((t_id, presence))

    _socket_boards.pop(sid, None)
    return results


def join_board(board_id: str, sid: str) -> None:
    if sid not in _socket_boards:
        _socket_boards[sid] = set()
    _socket_boards[sid].add(board_id)


def leave_board(board_id: str, sid: str) -> None:
    if sid in _socket_boards:
        _socket_boards[sid].discard(board_id)


def get_socket_boards(sid: str) -> set[str]:
    return set(_socket_boards.get(sid, set()))
