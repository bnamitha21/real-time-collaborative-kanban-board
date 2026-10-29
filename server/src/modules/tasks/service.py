import json
from typing import Any

from fractional_indexing import (  # type: ignore[import-untyped]
    generate_key_between,
    generate_n_keys_between,
)
from psycopg import Connection
from server.src.db.pool import with_tenant
from server.src.lib.errors import VersionConflict, bad_request, forbidden, not_found
from server.src.modules.access.permissions import can
from server.src.modules.activity.log import log_activity


def row_to_task_dto(row: Any) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "tenantId": str(row[1]),
        "boardId": str(row[2]),
        "columnId": str(row[3]),
        "title": row[4],
        "description": row[5],
        "assigneeId": str(row[6]) if row[6] else None,
        "priority": row[7],
        "position": row[8],
        "version": row[9],
        "createdBy": str(row[10]) if row[10] else None,
        "createdAt": row[11].isoformat() if hasattr(row[11], "isoformat") else str(row[11]),
        "updatedAt": row[12].isoformat() if hasattr(row[12], "isoformat") else str(row[12]),
    }


def verify_assignee(conn: Connection, org_id: str, tenant_id: str, assignee_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM memberships
            WHERE user_id = %s
              AND organization_id = %s
              AND (tenant_id = %s OR role = 'org_admin');
            """,
            (assignee_id, org_id, tenant_id),
        )
        if not cur.fetchone():
            raise bad_request("Assignee does not belong to this branch")


def create_task(
    org_id: str,
    tenant_id: str,
    user_id: str,
    board_id: str,
    column_id: str,
    title: str,
    description: str = "",
    assignee_id: str | None = None,
    priority: str = "medium",
    action_id: str | None = None,
) -> tuple[dict[str, Any], bool]:
    def _create(conn: Connection) -> tuple[dict[str, Any], bool]:
        with conn.cursor() as cur:
            # 1. Idempotency check
            if action_id:
                cur.execute(
                    "SELECT result FROM processed_actions WHERE action_id = %s AND tenant_id = %s;",
                    (action_id, tenant_id),
                )
                seen = cur.fetchone()
                if seen:
                    return seen[0], True

            # 2. Check destination column belongs to this board and tenant
            cur.execute(
                "SELECT id FROM columns WHERE id = %s AND board_id = %s AND tenant_id = %s;",
                (column_id, board_id, tenant_id),
            )
            if not cur.fetchone():
                raise bad_request("Column does not belong to this board")

            # 3. Check assignee belongs to this tenant/org
            if assignee_id:
                verify_assignee(conn, org_id, tenant_id, assignee_id)

            # 4. Compute fractional position at bottom of the column
            cur.execute(
                """
                SELECT position FROM tasks
                WHERE tenant_id = %s AND column_id = %s
                ORDER BY position COLLATE "C" DESC
                LIMIT 1;
                """,
                (tenant_id, column_id),
            )
            last_row = cur.fetchone()
            last_pos = last_row[0] if last_row else None
            new_pos = generate_key_between(last_pos, None)

            # 5. Insert task
            cur.execute(
                """
                INSERT INTO tasks (
                    tenant_id, board_id, column_id, title,
                    description, assignee_id, priority, position,
                    version, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                RETURNING id, tenant_id, board_id, column_id, title,
                          description, assignee_id, priority, position,
                          version, created_by, created_at, updated_at;
                """,
                (
                    tenant_id,
                    board_id,
                    column_id,
                    title,
                    description,
                    assignee_id,
                    priority,
                    new_pos,
                    user_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise bad_request("Failed to create task")
            task = row_to_task_dto(row)

            # 6. Audit logs
            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action="task.created",
                board_id=board_id,
                task_id=task["id"],
                after={
                    "title": task["title"],
                    "columnId": task["columnId"],
                    "position": task["position"],
                    "version": task["version"],
                },
            )
            if assignee_id:
                log_activity(
                    conn,
                    organization_id=org_id,
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="task.assigned",
                    board_id=board_id,
                    task_id=task["id"],
                    after={"assigneeId": assignee_id},
                )

            # 7. Record idempotency if action_id provided
            if action_id:
                cur.execute(
                    """
                    INSERT INTO processed_actions (action_id, tenant_id, user_id, result)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (action_id, tenant_id, user_id, json.dumps(task)),
                )

            return task, False

    return with_tenant(tenant_id, _create)


def get_task(tenant_id: str, task_id: str) -> dict[str, Any]:
    def _get(conn: Connection) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, board_id, column_id, title,
                       description, assignee_id, priority, position,
                       version, created_by, created_at, updated_at
                FROM tasks
                WHERE id = %s AND tenant_id = %s;
                """,
                (task_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Task not found")
            return row_to_task_dto(row)

    return with_tenant(tenant_id, _get)


def update_task(
    org_id: str,
    tenant_id: str,
    user_id: str,
    caller_role: str,
    task_id: str,
    expected_version: int,
    action_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    assignee_id: str | None = None,
    assignee_provided: bool = False,
    priority: str | None = None,
) -> tuple[dict[str, Any], bool]:
    def _update(conn: Connection) -> tuple[dict[str, Any], bool]:
        with conn.cursor() as cur:
            # 1. Idempotency check
            if action_id:
                cur.execute(
                    "SELECT result FROM processed_actions WHERE action_id = %s AND tenant_id = %s;",
                    (action_id, tenant_id),
                )
                seen = cur.fetchone()
                if seen:
                    return seen[0], True

            # 2. Lock row FOR UPDATE
            cur.execute(
                """
                SELECT id, tenant_id, board_id, column_id, title,
                       description, assignee_id, priority, position,
                       version, created_by, created_at, updated_at
                FROM tasks
                WHERE id = %s AND tenant_id = %s
                FOR UPDATE;
                """,
                (task_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Task not found")
            current_task = row_to_task_dto(row)

            # 3. Check permissions
            is_assignee = current_task["assigneeId"] == user_id
            if not can(caller_role, "task.update", {"is_assignee": is_assignee}):  # type: ignore[arg-type]
                raise forbidden("You do not have permission to update this task")

            # If assigning or unassigning, check task.assign permission
            if assignee_provided:
                if not can(caller_role, "task.assign"):  # type: ignore[arg-type]
                    raise forbidden("Members cannot reassign tasks")
                if assignee_id:
                    verify_assignee(conn, org_id, tenant_id, assignee_id)

            # 4. Check optimistic concurrency version
            if current_task["version"] != expected_version:
                raise VersionConflict(current=current_task)

            # 5. Build updates
            new_title = title if title is not None else current_task["title"]
            new_desc = description if description is not None else current_task["description"]
            new_assignee = assignee_id if assignee_provided else current_task["assigneeId"]
            new_priority = priority if priority is not None else current_task["priority"]

            cur.execute(
                """
                UPDATE tasks
                SET title = %s,
                    description = %s,
                    assignee_id = %s,
                    priority = %s,
                    version = version + 1
                WHERE id = %s AND tenant_id = %s AND version = %s
                RETURNING id, tenant_id, board_id, column_id, title,
                          description, assignee_id, priority, position,
                          version, created_by, created_at, updated_at;
                """,
                (
                    new_title,
                    new_desc,
                    new_assignee,
                    new_priority,
                    task_id,
                    tenant_id,
                    expected_version,
                ),
            )
            up_row = cur.fetchone()
            if not up_row:
                raise VersionConflict(current=current_task)
            updated_task = row_to_task_dto(up_row)

            # 6. Activity log
            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action="task.updated",
                board_id=current_task["boardId"],
                task_id=task_id,
                before={
                    "title": current_task["title"],
                    "description": current_task["description"],
                    "priority": current_task["priority"],
                    "version": current_task["version"],
                },
                after={
                    "title": updated_task["title"],
                    "description": updated_task["description"],
                    "priority": updated_task["priority"],
                    "version": updated_task["version"],
                },
            )

            if assignee_provided and new_assignee != current_task["assigneeId"]:
                log_activity(
                    conn,
                    organization_id=org_id,
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="task.assigned",
                    board_id=current_task["boardId"],
                    task_id=task_id,
                    before={"assigneeId": current_task["assigneeId"]},
                    after={"assigneeId": new_assignee},
                )

            # 7. Record idempotency
            if action_id:
                cur.execute(
                    """
                    INSERT INTO processed_actions (action_id, tenant_id, user_id, result)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (action_id, tenant_id, user_id, json.dumps(updated_task)),
                )

            return updated_task, False

    return with_tenant(tenant_id, _update)


def delete_task(
    org_id: str,
    tenant_id: str,
    user_id: str,
    caller_role: str,
    task_id: str,
    expected_version: int,
    action_id: str | None = None,
) -> bool:
    def _delete(conn: Connection) -> bool:
        with conn.cursor() as cur:
            # 1. Idempotency check
            if action_id:
                cur.execute(
                    "SELECT result FROM processed_actions WHERE action_id = %s AND tenant_id = %s;",
                    (action_id, tenant_id),
                )
                if cur.fetchone():
                    return True

            # 2. Lock row
            cur.execute(
                """
                SELECT id, tenant_id, board_id, column_id, title,
                       description, assignee_id, priority, position,
                       version, created_by, created_at, updated_at
                FROM tasks
                WHERE id = %s AND tenant_id = %s
                FOR UPDATE;
                """,
                (task_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Task not found")
            current_task = row_to_task_dto(row)

            # 3. Check permission
            if not can(caller_role, "task.delete"):  # type: ignore[arg-type]
                raise forbidden("You do not have permission to delete this task")

            # 4. Check version
            if current_task["version"] != expected_version:
                raise VersionConflict(current=current_task)

            # 5. Delete task
            cur.execute("DELETE FROM tasks WHERE id = %s AND tenant_id = %s;", (task_id, tenant_id))

            # 6. Log activity
            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action="task.deleted",
                board_id=current_task["boardId"],
                task_id=task_id,
                before={"title": current_task["title"], "version": current_task["version"]},
            )

            # 7. Record idempotency
            if action_id:
                cur.execute(
                    """
                    INSERT INTO processed_actions (action_id, tenant_id, user_id, result)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (action_id, tenant_id, user_id, json.dumps({"deleted": True})),
                )

            return False

    return with_tenant(tenant_id, _delete)


def rebalance_column(conn: Connection, tenant_id: str, column_id: str) -> None:
    with conn.cursor() as cur:
        # Fetch current order of tasks in the column
        cur.execute(
            """
            SELECT id FROM tasks
            WHERE column_id = %s AND tenant_id = %s
            ORDER BY position COLLATE "C" ASC, id ASC;
            """,
            (column_id, tenant_id),
        )
        ordered_ids = [str(r[0]) for r in cur.fetchall()]
        if not ordered_ids:
            return

        # Lock rows in deterministic order: id ascending (step 5.4 deadlock avoidance)
        cur.execute(
            """
            SELECT id FROM tasks
            WHERE column_id = %s AND tenant_id = %s
            ORDER BY id ASC
            FOR UPDATE;
            """,
            (column_id, tenant_id),
        )

        # Generate balanced keys
        new_keys = generate_n_keys_between(None, None, len(ordered_ids))
        for task_id, new_key in zip(ordered_ids, new_keys, strict=True):
            cur.execute(
                """
                UPDATE tasks
                SET position = %s, version = version + 1
                WHERE id = %s AND tenant_id = %s;
                """,
                (new_key, task_id, tenant_id),
            )


def move_task(
    org_id: str,
    tenant_id: str,
    user_id: str,
    caller_role: str,
    task_id: str,
    expected_version: int,
    to_column_id: str,
    after_task_id: str | None = None,
    action_id: str | None = None,
) -> tuple[dict[str, Any], bool, str, bool, str]:
    """Move or reorder a task.

    Returns: (updated_task, replayed, event_type, rebalanced, from_column_id)
    """

    def _move(conn: Connection) -> tuple[dict[str, Any], bool, str, bool, str]:
        with conn.cursor() as cur:
            # 1. Idempotency: a retried action returns the first result
            if action_id:
                cur.execute(
                    "SELECT result FROM processed_actions WHERE action_id = %s AND tenant_id = %s;",
                    (action_id, tenant_id),
                )
                seen = cur.fetchone()
                if seen:
                    cached_result = seen[0] if isinstance(seen[0], dict) else json.loads(seen[0])
                    return cached_result, True, "replayed", False, ""

            # 2. Take the row lock; concurrent movers queue here
            cur.execute(
                """
                SELECT id, tenant_id, board_id, column_id, title,
                       description, assignee_id, priority, position,
                       version, created_by, created_at, updated_at
                FROM tasks
                WHERE id = %s AND tenant_id = %s
                FOR UPDATE;
                """,
                (task_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                raise not_found("Task not found")
            current_task = row_to_task_dto(row)

            # 3. Permission (member only for own tasks)
            is_assignee = current_task["assigneeId"] == user_id
            if not can(caller_role, "task.move", {"is_assignee": is_assignee}):  # type: ignore[arg-type]
                raise forbidden("You do not have permission to move this task")

            # 4. Optimistic concurrency check
            if current_task["version"] != expected_version:
                raise VersionConflict(current=current_task)

            # 5. Destination column must belong to the same board
            cur.execute(
                "SELECT id, key FROM columns WHERE id = %s AND board_id = %s AND tenant_id = %s;",
                (to_column_id, current_task["boardId"], tenant_id),
            )
            if not cur.fetchone():
                raise bad_request("Destination column is not on this board")

            # 6. Neighbours computed server-side from current data
            prev_pos: str | None = None
            if after_task_id:
                cur.execute(
                    """
                    SELECT position FROM tasks
                    WHERE id = %s AND column_id = %s AND tenant_id = %s AND id <> %s;
                    """,
                    (after_task_id, to_column_id, tenant_id, task_id),
                )
                a_row = cur.fetchone()
                if not a_row:
                    raise bad_request("afterTaskId is not in the destination column")
                prev_pos = a_row[0]

            cur.execute(
                """
                SELECT position FROM tasks
                WHERE column_id = %s AND tenant_id = %s AND id <> %s
                  AND (%s::text IS NULL OR position COLLATE "C" > %s::text COLLATE "C")
                ORDER BY position COLLATE "C" ASC, id ASC
                LIMIT 1;
                """,
                (to_column_id, tenant_id, task_id, prev_pos, prev_pos),
            )
            next_row = cur.fetchone()
            next_pos: str | None = next_row[0] if next_row else None

            position = generate_key_between(prev_pos, next_pos)

            # 7. Write + Version bump
            cur.execute(
                """
                UPDATE tasks
                SET column_id = %s, position = %s, version = version + 1
                WHERE id = %s AND tenant_id = %s AND version = %s
                RETURNING id, tenant_id, board_id, column_id, title,
                          description, assignee_id, priority, position,
                          version, created_by, created_at, updated_at;
                """,
                (to_column_id, position, task_id, tenant_id, expected_version),
            )
            up_row = cur.fetchone()
            if not up_row:
                raise VersionConflict(current=current_task)
            updated_task = row_to_task_dto(up_row)

            # 8. Audit + Idempotency record, same transaction
            same_column = current_task["columnId"] == to_column_id
            action = "task.reordered" if same_column else "task.moved"
            event_type = "task:reordered" if same_column else "task:moved"
            from_column_id = current_task["columnId"]

            log_activity(
                conn,
                organization_id=org_id,
                tenant_id=tenant_id,
                actor_id=user_id,
                action=action,
                board_id=current_task["boardId"],
                task_id=task_id,
                before={
                    "title": current_task["title"],
                    "columnId": current_task["columnId"],
                    "position": current_task["position"],
                    "version": current_task["version"],
                },
                after={
                    "title": updated_task["title"],
                    "columnId": to_column_id,
                    "position": position,
                    "version": updated_task["version"],
                },
            )

            if action_id:
                cur.execute(
                    """
                    INSERT INTO processed_actions (action_id, tenant_id, user_id, result)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (action_id, tenant_id, user_id, json.dumps(updated_task)),
                )

            # 9. Rebalancing safeguard (step 5.3): fractional key length > 64
            rebalanced = False
            if len(position) > 64:
                rebalance_column(conn, tenant_id, to_column_id)
                rebalanced = True
                cur.execute(
                    """
                    SELECT id, tenant_id, board_id, column_id, title,
                           description, assignee_id, priority, position,
                           version, created_by, created_at, updated_at
                    FROM tasks
                    WHERE id = %s AND tenant_id = %s;
                    """,
                    (task_id, tenant_id),
                )
                refreshed = cur.fetchone()
                if refreshed:
                    updated_task = row_to_task_dto(refreshed)

            return updated_task, False, event_type, rebalanced, from_column_id

    return with_tenant(tenant_id, _move)
