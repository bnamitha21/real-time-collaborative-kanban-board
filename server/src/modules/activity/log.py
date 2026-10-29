import json
from typing import Any

from psycopg import Connection


def log_activity(
    conn: Connection,
    organization_id: str,
    tenant_id: str,
    actor_id: str | None,
    action: str,
    board_id: str | None = None,
    task_id: str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO activity_logs (
                organization_id, tenant_id, board_id, task_id,
                actor_id, action, before_value, after_value
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                organization_id,
                tenant_id,
                board_id,
                task_id,
                actor_id,
                action,
                json.dumps(before) if before is not None else None,
                json.dumps(after) if after is not None else None,
            ),
        )
