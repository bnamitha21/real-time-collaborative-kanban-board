import os
from collections.abc import Callable
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg import Connection
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kanban_app:app_pw@localhost:5432/kanban"
)

DATABASE_URL_OWNER = os.environ.get(
    "DATABASE_URL_OWNER",
    "postgresql://owner:owner_pw@localhost:5432/kanban"
)

# Connection pool for application queries (runs under kanban_app role with RLS enabled)
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=20,
    open=False,
)

def get_connection() -> Connection:
    if not pool.closed:
        return pool.getconn()
    return psycopg.connect(DATABASE_URL)

@contextmanager
def transaction(conn: Connection | None = None):
    own_conn = False
    if conn is None:
        conn = psycopg.connect(DATABASE_URL)
        own_conn = True
    try:
        with conn.transaction():
            yield conn
    finally:
        if own_conn:
            conn.close()

def with_tx[T](fn: Callable[[Connection], T], connection_url: str | None = None) -> T:
    url = connection_url or DATABASE_URL
    with psycopg.connect(url) as conn, conn.transaction():
        return fn(conn)

def with_tenant[T](tenant_id: str, fn: Callable[[Connection], T], connection_url: str | None = None) -> T:
    """Every tenant-scoped query must run through with_tenant so that
    app.tenant_id is set for PostgreSQL Row Level Security (RLS)."""
    url = connection_url or DATABASE_URL
    with psycopg.connect(url) as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true);", (str(tenant_id),))
        return fn(conn)
