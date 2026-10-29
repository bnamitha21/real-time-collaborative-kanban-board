import logging
import uuid

import psycopg
from flask import Flask, g, jsonify, request
from flask_cors import CORS

from server.src.config.env import env
from server.src.db.pool import DATABASE_URL
from server.src.lib.errors import AppError
from server.src.modules.access.routes import workspaces_bp
from server.src.modules.auth.routes import auth_bp

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, env.LOG_LEVEL.upper(), logging.INFO),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("kanban_server")

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024  # 100 kB body limit

    # CORS configuration
    CORS(
        app,
        origins=[env.CLIENT_ORIGIN],
        supports_credentials=True,
    )

    # Middleware: Request ID and logging
    @app.before_request
    def set_request_context():
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.request_id = req_id

    @app.after_request
    def apply_security_headers(response):
        # Security headers
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Cache-Control"] = "no-store"
        return response

    # Health endpoints
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    @app.get("/readyz")
    def readyz():
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return jsonify({"status": "ready"}), 200
        except (psycopg.Error, OSError) as e:
            logger.error(f"Readiness check failed: {e}")
            return jsonify({"error": {"code": "INTERNAL", "message": "Database unavailable"}}), 503

    # Mount routes
    app.register_blueprint(auth_bp)
    app.register_blueprint(workspaces_bp)

    # Error handlers
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        return jsonify(err.to_dict()), err.status

    @app.errorhandler(404)
    def handle_not_found(_err):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found"}}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_err):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Method not allowed"}}), 404

    @app.errorhandler(413)
    def handle_large_payload(_err):
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Payload exceeds 100 kB limit"}}), 400

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        req_id = getattr(g, "request_id", "unknown")
        logger.error(f"[{req_id}] Unexpected internal error: {err}")
        return jsonify({"error": {"code": "INTERNAL", "message": "An internal error occurred."}}), 500

    return app
