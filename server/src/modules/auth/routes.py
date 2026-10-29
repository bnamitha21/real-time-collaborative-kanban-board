from flask import Blueprint, g, jsonify, make_response, request
from psycopg import errors as pg_errors

from server.src.config.env import env
from server.src.db.pool import with_tx
from server.src.lib.errors import bad_request, unauthenticated
from server.src.middleware.authenticate import authenticate
from server.src.middleware.rate_limit import rate_limit
from server.src.middleware.validate import validate_request
from server.src.modules.auth.password import hash_password, verify_password
from server.src.modules.auth.schemas import LoginInput, RegisterInput
from server.src.modules.auth.tokens import (
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

REFRESH_COOKIE_NAME = "refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

def set_refresh_cookie(response, token: str) -> None:
    max_age = env.REFRESH_TTL_DAYS * 24 * 60 * 60
    is_prod = env.FLASK_ENV == "production"
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=is_prod,
        samesite="Lax",
        path=REFRESH_COOKIE_PATH,
    )

def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )

@auth_bp.post("/register")
@rate_limit(max_requests=10, window_seconds=60)
@validate_request(body_model=RegisterInput)
def register():
    data: RegisterInput = g.validated_body
    pw_hash = hash_password(data.password)

    def _insert(conn):
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO users (email, name, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, email, name, created_at;
                    """,
                    (data.email.lower(), data.name, pw_hash),
                )
                row = cur.fetchone()
                assert row is not None
                return {"id": str(row[0]), "email": str(row[1]), "name": str(row[2])}
            except pg_errors.UniqueViolation as err:
                raise bad_request("Email already in use") from err

    user_info = with_tx(_insert)
    return jsonify({"data": user_info}), 201

@auth_bp.post("/login")
@rate_limit(max_requests=10, window_seconds=60)
@validate_request(body_model=LoginInput)
def login():
    data: LoginInput = g.validated_body

    def _login(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, name, password_hash
                FROM users
                WHERE email = %s;
                """,
                (data.email.lower(),),
            )
            row = cur.fetchone()
            if not row:
                raise bad_request("Invalid email or password")

            user_id, email, name, password_hash = row
            if not verify_password(password_hash, data.password):
                raise bad_request("Invalid email or password")

            user_data = {"id": str(user_id), "email": str(email), "name": str(name)}
            access_token = create_access_token(user_id)
            refresh_token = create_refresh_token(user_id, conn)
            return access_token, refresh_token, user_data

    access_token, refresh_token, user = with_tx(_login)
    resp = make_response(jsonify({"data": {"accessToken": access_token, "user": user}}), 200)
    set_refresh_cookie(resp, refresh_token)
    return resp

@auth_bp.post("/refresh")
def refresh():
    raw_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_cookie:
        raise unauthenticated("Refresh token missing")

    access_token, new_refresh_token, user = with_tx(
        lambda conn: rotate_refresh_token(raw_cookie, conn)
    )

    if user.get("revoked_due_to_reuse"):
        err = unauthenticated("Session revoked due to token reuse")
        resp = make_response(jsonify(err.to_dict()), 401)
        clear_refresh_cookie(resp)
        return resp

    assert new_refresh_token is not None
    resp = make_response(jsonify({"data": {"accessToken": access_token, "user": user}}), 200)
    set_refresh_cookie(resp, new_refresh_token)
    return resp

@auth_bp.post("/logout")
def logout():
    raw_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_cookie:
        with_tx(lambda conn: revoke_refresh_token(raw_cookie, conn))

    resp = make_response(jsonify({"data": {"success": True}}), 200)
    clear_refresh_cookie(resp)
    return resp

@auth_bp.get("/me")
@authenticate
def me():
    user_id = g.user_id

    def _get_user(conn):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, created_at FROM users WHERE id = %s;",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                raise unauthenticated("User not found")
            return {
                "id": str(row[0]),
                "email": str(row[1]),
                "name": str(row[2]),
                "createdAt": row[3].isoformat(),
            }

    user = with_tx(_get_user)
    return jsonify({"data": user}), 200
