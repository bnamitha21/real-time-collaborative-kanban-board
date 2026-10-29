export type Role = "org_admin" | "tenant_admin" | "member";

export type PermissionAction =
  | "board:create"
  | "board:read"
  | "board:update"
  | "board:delete"
  | "column:rename"
  | "task:create"
  | "task:read"
  | "task:update"
  | "task:move"
  | "task:delete"
  | "activity:read";

export interface PermissionContext {
  isAssignee?: boolean;
}

export function can(
  role: Role | null | undefined,
  action: PermissionAction,
  ctx: PermissionContext = {},
): boolean {
  if (!role) return false;

  // Org admin and tenant admin have full control within scope
  if (role === "org_admin" || role === "tenant_admin") {
    return true;
  }

  // Member permissions
  if (role === "member") {
    switch (action) {
      case "board:read":
      case "task:read":
      case "activity:read":
        return true;
      case "task:move":
      case "task:update":
        return Boolean(ctx.isAssignee);
      case "board:create":
      case "board:update":
      case "board:delete":
      case "column:rename":
      case "task:create":
      case "task:delete":
        return false;
      default:
        return false;
    }
  }

  return false;
}

