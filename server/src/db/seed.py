import os
import sys

import psycopg
from argon2 import PasswordHasher
from dotenv import load_dotenv
from fractional_indexing import generate_key_between  # type: ignore[import-untyped]

load_dotenv()

ph = PasswordHasher()

def seed(conn_str: str | None = None) -> None:
    env_name = os.environ.get("FLASK_ENV", "development").lower()
    if env_name == "production":
        print("Refusing to seed in production environment!", file=sys.stderr)
        sys.exit(1)

    url = conn_str or os.environ.get("DATABASE_URL_OWNER")
    if not url:
        print("DATABASE_URL_OWNER is required to run seed.", file=sys.stderr)
        sys.exit(1)

    default_pw_hash = ph.hash("Passw0rd!")

    with psycopg.connect(url) as conn, conn.transaction(), conn.cursor() as cur:
        # 1. Clean existing seed data
        cur.execute("TRUNCATE activity_logs, processed_actions, tasks, columns, boards, memberships, tenants, organizations, refresh_tokens, users CASCADE;")

        # 2. Users
        users_data = [
            ("orgadmin@northwind.test", "Northwind Org Admin"),
            ("admin.hyd@northwind.test", "Hyderabad Tenant Admin"),
            ("member.hyd@northwind.test", "Hyderabad Member 1"),
            ("member2.hyd@northwind.test", "Hyderabad Member 2"),
            ("admin.vja@northwind.test", "Vijayawada Tenant Admin"),
            ("admin@contoso.test", "Contoso Org Admin"),
            ("multi@northwind.test", "Multi-branch Member"),
        ]
        user_ids = {}
        for email, name in users_data:
            cur.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s) RETURNING id;",
                (email, name, default_pw_hash)
            )
            row = cur.fetchone()
            assert row is not None
            user_ids[email] = row[0]

        # 3. Organizations
        cur.execute("INSERT INTO organizations (name) VALUES (%s) RETURNING id;", ("Northwind Traders",))
        row = cur.fetchone()
        assert row is not None
        northwind_id = row[0]

        cur.execute("INSERT INTO organizations (name) VALUES (%s) RETURNING id;", ("Contoso Retail",))
        row = cur.fetchone()
        assert row is not None
        contoso_id = row[0]

        # 4. Tenants (Branches)
        cur.execute("INSERT INTO tenants (organization_id, name) VALUES (%s, %s) RETURNING id;", (northwind_id, "Hyderabad"))
        row = cur.fetchone()
        assert row is not None
        hyd_id = row[0]

        cur.execute("INSERT INTO tenants (organization_id, name) VALUES (%s, %s) RETURNING id;", (northwind_id, "Vijayawada"))
        row = cur.fetchone()
        assert row is not None
        vja_id = row[0]

        cur.execute("INSERT INTO tenants (organization_id, name) VALUES (%s, %s) RETURNING id;", (contoso_id, "Chennai"))
        row = cur.fetchone()
        assert row is not None
        chennai_id = row[0]

        # 5. Memberships
        memberships = [
            (user_ids["orgadmin@northwind.test"], northwind_id, None, "org_admin"),
            (user_ids["admin.hyd@northwind.test"], northwind_id, hyd_id, "tenant_admin"),
            (user_ids["member.hyd@northwind.test"], northwind_id, hyd_id, "member"),
            (user_ids["member2.hyd@northwind.test"], northwind_id, hyd_id, "member"),
            (user_ids["admin.vja@northwind.test"], northwind_id, vja_id, "tenant_admin"),
            (user_ids["multi@northwind.test"], northwind_id, hyd_id, "member"),
            (user_ids["multi@northwind.test"], northwind_id, vja_id, "member"),
            (user_ids["admin@contoso.test"], contoso_id, None, "org_admin"),
        ]
        for u_id, o_id, t_id, role in memberships:
            cur.execute(
                "INSERT INTO memberships (user_id, organization_id, tenant_id, role) VALUES (%s, %s, %s, %s);",
                (u_id, o_id, t_id, role)
            )

        # 6. Boards and Columns for each branch
        branches = [
            (northwind_id, hyd_id, user_ids["admin.hyd@northwind.test"]),
            (northwind_id, vja_id, user_ids["admin.vja@northwind.test"]),
            (contoso_id, chennai_id, user_ids["admin@contoso.test"]),
        ]
        branch_boards = {}
        branch_columns = {}

        for o_id, t_id, creator_id in branches:
            cur.execute(
                "INSERT INTO boards (organization_id, tenant_id, name, created_by) VALUES (%s, %s, %s, %s) RETURNING id;",
                (o_id, t_id, "Sprint Board", creator_id)
            )
            row = cur.fetchone()
            assert row is not None
            board_id = row[0]
            branch_boards[t_id] = board_id

            cols = [("todo", "To Do", 0), ("in_progress", "In Progress", 1), ("completed", "Completed", 2)]
            cols_map = {}
            for key, name, pos in cols:
                cur.execute(
                    "INSERT INTO columns (tenant_id, board_id, key, name, position) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                    (t_id, board_id, key, name, pos)
                )
                col_row = cur.fetchone()
                assert col_row is not None
                cols_map[key] = col_row[0]
            branch_columns[t_id] = cols_map

        # 7. Hyderabad tasks in To Do column
        hyd_board = branch_boards[hyd_id]
        hyd_todo = branch_columns[hyd_id]["todo"]
        creator = user_ids["admin.hyd@northwind.test"]
        assignee = user_ids["member.hyd@northwind.test"]

        pos1 = generate_key_between(None, None)
        pos2 = generate_key_between(pos1, None)
        pos3 = generate_key_between(pos2, None)

        tasks = [
            ("Build Login Page", "Implement responsive login page", assignee, pos1, "high"),
            ("Design Homepage", "Design UI mockup and wireframes", assignee, pos2, "medium"),
            ("Fix API Bug", "Resolve concurrency issue on update API", assignee, pos3, "high"),
        ]

        for title, desc, assigned, pos, prio in tasks:
            cur.execute(
                """
                INSERT INTO tasks (tenant_id, board_id, column_id, title, description, assignee_id, position, priority, version, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s);
                """,
                (hyd_id, hyd_board, hyd_todo, title, desc, assigned, pos, prio, creator)
            )

        print("Seed data successfully inserted.")

if __name__ == "__main__":
    seed()
