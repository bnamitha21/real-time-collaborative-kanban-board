import logging

from server.src.app import create_app
from server.src.config.env import env
from server.src.db.migrate import run_migrations
from server.src.db.pool import DATABASE_URL_OWNER
from server.src.realtime.socket import socketio

logger = logging.getLogger("kanban_server")

app = create_app()

if __name__ == "__main__":
    # Auto-run migrations on startup (uses owner connection)
    if DATABASE_URL_OWNER:
        logger.info("Running database migrations...")
        try:
            run_migrations(DATABASE_URL_OWNER)
            logger.info("Migrations complete.")
        except Exception as exc:
            logger.error(f"Migration failed: {exc}")
            raise SystemExit(1) from exc
    else:
        logger.warning(
            "DATABASE_URL_OWNER not set — skipping automatic migrations. "
            "Run 'python scripts/init_db.py' manually."
        )

    print(f"Starting server on port {env.PORT}...")
    socketio.run(
        app,
        host="0.0.0.0",
        port=env.PORT,
        debug=env.FLASK_ENV == "development",
        allow_unsafe_werkzeug=True,
    )
