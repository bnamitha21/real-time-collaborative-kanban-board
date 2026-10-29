import time
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import request

from server.src.lib.errors import rate_limited

_request_log: dict[str, list[float]] = defaultdict(list)

def rate_limit(max_requests: int = 10, window_seconds: int = 60) -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            key = f"{request.endpoint}:{ip}"
            now = time.time()
            cutoff = now - window_seconds

            # Filter out timestamps older than the window
            timestamps = [t for t in _request_log[key] if t > cutoff]
            if len(timestamps) >= max_requests:
                raise rate_limited("Too many requests, please slow down.")

            timestamps.append(now)
            _request_log[key] = timestamps
            return fn(*args, **kwargs)

        return wrapper

    return decorator

def reset_rate_limits() -> None:
    _request_log.clear()
