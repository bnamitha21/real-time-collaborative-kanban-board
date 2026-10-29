import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, request
from pydantic import BaseModel, ValidationError

from server.src.lib.errors import bad_request


def validate_uuid(val: Any, param_name: str) -> None:
    try:
        uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        raise bad_request(f"Invalid UUID for parameter: {param_name}")


def validate_request(
    body_model: type[BaseModel] | None = None,
    query_model: type[BaseModel] | None = None,
    params_model: type[BaseModel] | None = None,
) -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Auto-validate any path parameter ending in _id or Id as UUID
                for k, v in kwargs.items():
                    if k.endswith(("_id", "Id")):
                        validate_uuid(v, k)

                if params_model is not None:
                    g.validated_params = params_model.model_validate(kwargs)

                if body_model is not None:
                    # Enforce JSON Content-Type and payload
                    json_data = request.get_json(silent=True)
                    if json_data is None and request.content_length and request.content_length > 0:
                        raise bad_request("Invalid JSON payload")
                    if json_data is None:
                        json_data = {}
                    g.validated_body = body_model.model_validate(json_data)

                if query_model is not None:
                    query_dict = request.args.to_dict()
                    g.validated_query = query_model.model_validate(query_dict)

            except ValidationError as err:
                details = [
                    {
                        "field": ".".join(str(loc) for loc in e["loc"]),
                        "message": e["msg"],
                        "type": e["type"],
                    }
                    for e in err.errors()
                ]
                first_msg = details[0]["message"] if details else "Validation failed"
                raise bad_request(f"Validation error: {first_msg}", details=details) from err

            return fn(*args, **kwargs)

        return wrapper

    return decorator
