from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, request

from server.src.lib.errors import unauthenticated
from server.src.modules.auth.tokens import verify_access_token


def authenticate(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise unauthenticated("Authentication required")

        token = auth_header.split(" ", 1)[1].strip()
        user_id = verify_access_token(token)
        g.user_id = user_id
        return fn(*args, **kwargs)

    return wrapper
