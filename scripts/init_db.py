#!/usr/bin/env python3
"""
init_db.py — Local PostgreSQL database initializer for Kanban Board.

Usage:
    python scripts/init_db.py [--seed] [--reset]

Requires:
    - PostgreSQL running locally on port 5432
    - A superuser/admin connection (default: postgres/postgres)
    - .venv activated, or run via: .venv/Scripts/python scripts/init_db.py

What it does:
    1. Creates the `kanban` database (as superuser)
    2. Creates the `owner` role with CREATE privileges
    3. Creates the `kanban_app` role (restricted, for app queries with RLS)
    4. Runs all SQL migrations from server/migrations/
    5. Optionally seeds development data (--seed)
    6. Optionally drops and recreates the DB first (--reset)
"""

import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Allow running from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_superuser_dsn(host: str = "localhost", port: int = 5432) -> str:
    """Build superuser DSN from environment or defaults."""
    pg_user = os.environ.get("PGUSER", "postgres")
    pg_pass = os.environ.get("PGPASSWORD", "postgres")
    pg_host = os.environ.get("PGHOST", host)
    pg_port = os.environ.get("PGPORT", str(port))
    # Connect to 'postgres' maintenance DB
    return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/postgres"


def run_sql(conn, sql: str, params=None) -> None:
    """Execute SQL, ignoring minor errors if needed."""
    with conn.cursor() as cur:
        cur.execute(sql, params)


def check_role_exists(conn, role_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (role_name,))
        return cur.fetchone() is not None


def check_db_exists(conn, db_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
        return cur.fetchone() is not None


def create_roles_and_db(
    superuser_dsn: str,
    db_name: str = "kanban",
    owner_user: str = "owner",
    owner_pw: str = "owner_pw",
    app_user: str = "kanban_app",
    app_pw: str = "app_pw",
    reset: bool = False,
) -> None:
    """Create roles and the database using the superuser connection."""
    import psycopg

    print(f"\n{'='*60}")
    print("Step 1: Connecting as PostgreSQL superuser...")
    print(f"{'='*60}")

    # autocommit=True needed for CREATE DATABASE
    with psycopg.connect(superuser_dsn, autocommit=True) as conn:

        # --- Optionally drop and recreate the DB ---
        if reset and check_db_exists(conn, db_name):
            print(f"  [RESET] Terminating existing connections to '{db_name}'...")
            run_sql(
                conn,
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid();
                """,
                (db_name,),
            )
            print(f"  [RESET] Dropping database '{db_name}'...")
            run_sql(conn, f'DROP DATABASE IF EXISTS "{db_name}";')

        # --- Create owner role ---
        from psycopg import sql
        if not check_role_exists(conn, owner_user):
            print(f"  Creating role '{owner_user}'...")
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} CREATEDB CREATEROLE;").format(
                        sql.Identifier(owner_user),
                        sql.Literal(owner_pw),
                    )
                )
        else:
            print(f"  Role '{owner_user}' already exists — skipping.")
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD {};").format(
                        sql.Identifier(owner_user),
                        sql.Literal(owner_pw),
                    )
                )

        # --- Create kanban_app role (no createdb, no superuser) ---
        if not check_role_exists(conn, app_user):
            print(f"  Creating role '{app_user}' (restricted app user)...")
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {};").format(
                        sql.Identifier(app_user),
                        sql.Literal(app_pw),
                    )
                )
        else:
            print(f"  Role '{app_user}' already exists — skipping.")
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD {};").format(
                        sql.Identifier(app_user),
                        sql.Literal(app_pw),
                    )
                )

        # --- Create database owned by owner role ---
        if not check_db_exists(conn, db_name):
            print(f"  Creating database '{db_name}' owned by '{owner_user}'...")
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {};").format(
                        sql.Identifier(db_name),
                        sql.Identifier(owner_user),
                    )
                )
        else:
            print(f"  Database '{db_name}' already exists — skipping.")

    print("  [OK] Roles and database ready.\n")


def run_migrations(owner_dsn: str, migrations_dir: Path) -> None:
    """Run SQL migrations in order using the owner connection."""
    import psycopg

    print(f"{'='*60}")
    print("Step 2: Running migrations...")
    print(f"{'='*60}")

    sql_files = sorted([f for f in migrations_dir.iterdir() if f.suffix == ".sql"])
    if not sql_files:
        print("  No migration files found!")
        return

    with psycopg.connect(owner_dsn) as conn:
        # Create schema_migrations tracking table
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                );
            """)
        conn.commit()

        for sql_file in sql_files:
            file_name = sql_file.name
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE name = %s;", (file_name,)
                )
                if cur.fetchone() is not None:
                    print(f"  [SKIP]  {file_name} (already applied)")
                    continue

                content = sql_file.read_text(encoding="utf-8")
                print(f"  [RUN]   {file_name}...")
                try:
                    with conn.transaction():
                        cur.execute(content)
                        cur.execute(
                            "INSERT INTO schema_migrations (name) VALUES (%s);",
                            (file_name,),
                        )
                    print(f"  [OK]    {file_name}")
                except Exception as e:
                    print(f"  [FAIL]  {file_name}: {e}", file=sys.stderr)
                    raise

    print("  [OK] All migrations applied.\n")


def run_seed(owner_dsn: str) -> None:
    """Seed development data."""
    print(f"{'='*60}")
    print("Step 3: Seeding development data...")
    print(f"{'='*60}")

    from server.src.db.seed import seed

    seed(owner_dsn)
    print("  [OK] Seed data inserted.\n")


def verify_rls(app_dsn: str) -> None:
    """Verify RLS is working — queries without tenant context return 0 rows."""
    import psycopg

    print(f"{'='*60}")
    print("Step 4: Verifying Row Level Security (RLS)...")
    print(f"{'='*60}")

    with psycopg.connect(app_dsn) as conn:
        with conn.cursor() as cur:
            # Without app.tenant_id set, RLS should return 0 rows
            cur.execute("SELECT count(*) FROM boards;")
            row = cur.fetchone()
            count = row[0] if row else 0
            if count == 0:
                print("  [OK] RLS PASS: boards visible without tenant context = 0")
            else:
                print(
                    f"  [FAIL] RLS FAIL: boards visible without tenant context = {count}",
                    file=sys.stderr,
                )
                sys.exit(1)

            cur.execute("SELECT count(*) FROM tasks;")
            row = cur.fetchone()
            count = row[0] if row else 0
            if count == 0:
                print("  [OK] RLS PASS: tasks visible without tenant context = 0")
            else:
                print(
                    f"  [FAIL] RLS FAIL: tasks visible without tenant context = {count}",
                    file=sys.stderr,
                )
                sys.exit(1)

    print("  [OK] Row Level Security is properly enforced.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize local PostgreSQL database for Kanban Board"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Insert development seed data after migrations",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate the database (DESTRUCTIVE — dev only)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="PostgreSQL host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5432,
        help="PostgreSQL port (default: 5432)",
    )
    parser.add_argument(
        "--pg-user",
        default="postgres",
        help="PostgreSQL superuser name (default: postgres)",
    )
    parser.add_argument(
        "--pg-password",
        default="postgres",
        help="PostgreSQL superuser password (default: postgres)",
    )
    parser.add_argument(
        "--db-name",
        default="kanban",
        help="Database name to create (default: kanban)",
    )
    parser.add_argument(
        "--no-verify-rls",
        action="store_true",
        help="Skip RLS verification step",
    )
    args = parser.parse_args()

    # Override env vars if provided
    if args.pg_user:
        os.environ["PGUSER"] = args.pg_user
    if args.pg_password is not None:
        os.environ["PGPASSWORD"] = args.pg_password
    if args.host:
        os.environ["PGHOST"] = args.host
    if args.port:
        os.environ["PGPORT"] = str(args.port)

    # Connection strings
    auth_part = f"{args.pg_user}:{args.pg_password}" if args.pg_password else args.pg_user
    superuser_dsn = f"postgresql://{auth_part}@{args.host}:{args.port}/postgres"
    owner_dsn = f"postgresql://owner:owner_pw@{args.host}:{args.port}/{args.db_name}"
    app_dsn = f"postgresql://kanban_app:app_pw@{args.host}:{args.port}/{args.db_name}"

    # Migrations directory
    migrations_dir = PROJECT_ROOT / "server" / "migrations"
    if not migrations_dir.exists():
        print(f"Error: migrations directory not found at {migrations_dir}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  Kanban Board — Local PostgreSQL Setup")
    print("=" * 60)
    print(f"  Host:         {args.host}:{args.port}")
    print(f"  Database:     {args.db_name}")
    print(f"  Owner role:   owner / owner_pw")
    print(f"  App role:     kanban_app / app_pw (RLS enforced)")
    print(f"  Migrations:   {migrations_dir}")
    print(f"  Seed data:    {'yes' if args.seed else 'no'}")
    print(f"  Reset DB:     {'yes (DESTRUCTIVE)' if args.reset else 'no'}")
    print("=" * 60 + "\n")

    try:
        import psycopg  # noqa: F401
    except ImportError:
        print(
            "Error: psycopg not installed. Run: pip install psycopg[binary]",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Step 1: Create roles and DB
        create_roles_and_db(
            superuser_dsn,
            db_name=args.db_name,
            reset=args.reset,
        )

        # Step 2: Run migrations (as owner)
        run_migrations(owner_dsn, migrations_dir)

        # Step 3: Seed data (optional)
        if args.seed:
            run_seed(owner_dsn)

        # Step 4: Verify RLS
        if not args.no_verify_rls:
            verify_rls(app_dsn)

        print("=" * 60)
        print("  [OK] Database setup complete!")
        print("=" * 60)
        print()
        print("  Next steps:")
        print(f"  1. Ensure .env has:")
        print(f"       DATABASE_URL_OWNER=postgresql://owner:owner_pw@{args.host}:{args.port}/{args.db_name}")
        print(f"       DATABASE_URL=postgresql://kanban_app:app_pw@{args.host}:{args.port}/{args.db_name}")
        print(f"  2. Start the server:  cd kanban && .venv\\Scripts\\python -m server.src.main")
        if not args.seed:
            print(f"  3. Seed dev data:     .venv\\Scripts\\python scripts/init_db.py --seed")
        print()

    except Exception as e:
        print(f"\n[FAIL] Setup failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

