from typing import Any

from server.src.modules.access.access import Role

PERMISSIONS: dict[str, list[str]] = {
    "org.read": ["org_admin", "tenant_admin", "member"],
    "org.update": ["org_admin"],
    "org.delete": ["org_admin"],
    "tenant.create": ["org_admin"],
    "tenant.read": ["org_admin", "tenant_admin", "member"],
    "tenant.update": ["org_admin"],
    "tenant.delete": ["org_admin"],
    "board.read": ["org_admin", "tenant_admin", "member"],
    "board.create": ["org_admin", "tenant_admin"],
    "board.update": ["org_admin", "tenant_admin"],
    "board.delete": ["org_admin", "tenant_admin"],
    "column.read": ["org_admin", "tenant_admin", "member"],
    "column.update": ["org_admin", "tenant_admin"],
    "task.read": ["org_admin", "tenant_admin", "member"],
    "task.create": ["org_admin", "tenant_admin"],
    "task.assign": ["org_admin", "tenant_admin"],
    "task.delete": ["org_admin", "tenant_admin"],
    "task.update": ["org_admin", "tenant_admin", "member:own"],
    "task.move": ["org_admin", "tenant_admin", "member:own"],
    "activity.read": ["org_admin", "tenant_admin", "member"],
}


def can(
    role: Role,
    perm: str,
    ctx: dict[str, Any] | None = None,
) -> bool:
    allowed = PERMISSIONS.get(perm, [])
    if role in allowed:
        return True
    is_assignee = bool(ctx and (ctx.get("is_assignee") or ctx.get("isAssignee")))
    return bool(
        role == "member" and "member:own" in allowed and is_assignee
    )
