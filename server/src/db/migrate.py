import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

def run_migrations(connection_string: str | None = None) -> None:
    conn_str = connection_string or os.environ.get("DATABASE_URL_OWNER")
    if not conn_str:
        print("DATABASE_URL_OWNER environment variable is required for migrations.", file=sys.stderr)
        sys.exit(1)

    migrations_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
    sql_files = sorted([f for f in migrations_dir.iterdir() if f.suffix == ".sql"])

    with psycopg.connect(conn_str) as conn:
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
                cur.execute("SELECT 1 FROM schema_migrations WHERE name = %s;", (file_name,))
                if cur.fetchone() is not None:
                    continue

                content = sql_file.read_text(encoding="utf-8")
                print(f"Applying migration {file_name}...")
                with conn.transaction():
                    cur.execute(content)
                    cur.execute(
                        "INSERT INTO schema_migrations (name) VALUES (%s);",
                        (file_name,)
                    )
                print(f"Applied {file_name}")

if __name__ == "__main__":
    run_migrations()
