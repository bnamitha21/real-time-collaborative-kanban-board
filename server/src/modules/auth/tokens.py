import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from psycopg import Connection

from server.src.config.env import env
from server.src.lib.errors import unauthenticated


def create_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=env.JWT_ACCESS_TTL_SECONDS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, env.JWT_ACCESS_SECRET, algorithm="HS256")


def verify_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, env.JWT_ACCESS_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise unauthenticated("Invalid access token")
        return str(user_id)
    except jwt.ExpiredSignatureError as e:
        raise unauthenticated("Session expired") from e
    except jwt.PyJWTError as e:
        raise unauthenticated("Invalid access token") from e


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_refresh_token(user_id: str, conn: Connection) -> str:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=env.REFRESH_TTL_DAYS)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s);
            """,
            (user_id, token_hash, expires_at),
        )
    return raw_token


def rotate_refresh_token(
    raw_token: str, conn: Connection
) -> tuple[str | None, str | None, dict[str, Any]]:
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(UTC)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked_at, u.email, u.name
            FROM refresh_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token_hash = %s;
            """,
            (token_hash,),
        )
        row = cur.fetchone()

        if not row:
            raise unauthenticated("Invalid refresh token")

        rt_id, user_id, expires_at, revoked_at, email, name = row

        # If already revoked: Token reuse detected! Revoke all tokens for this user in DB
        if revoked_at is not None:
            cur.execute(
                "UPDATE refresh_tokens SET revoked_at = %s WHERE user_id = %s;",
                (now, user_id),
            )
            # Return flag so transaction commits before raising 401
            return None, None, {"revoked_due_to_reuse": True}

        if expires_at < now:
            raise unauthenticated("Refresh token expired")

        # Mark old token as revoked
        cur.execute(
            "UPDATE refresh_tokens SET revoked_at = %s WHERE id = %s;",
            (now, rt_id),
        )

    # Issue new access token and rotating refresh token
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id, conn)
    user_data = {"id": str(user_id), "email": str(email), "name": str(name)}

    return new_access_token, new_refresh_token, user_data


def revoke_refresh_token(raw_token: str, conn: Connection) -> None:
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(UTC)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE refresh_tokens SET revoked_at = %s WHERE token_hash = %s;",
            (now, token_hash),
        )
