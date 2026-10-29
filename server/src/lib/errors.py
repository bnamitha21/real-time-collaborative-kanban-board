from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        err_body: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            err_body["details"] = self.details
        return {"error": err_body}

def bad_request(message: str, details: Any = None) -> AppError:
    return AppError(400, "VALIDATION_ERROR", message, details)

def unauthenticated(message: str = "Authentication required", details: Any = None) -> AppError:
    return AppError(401, "UNAUTHENTICATED", message, details)

def forbidden(message: str = "You do not have permission to do this", details: Any = None) -> AppError:
    return AppError(403, "FORBIDDEN", message, details)

def not_found(message: str = "Not found", details: Any = None) -> AppError:
    return AppError(404, "NOT_FOUND", message, details)

class VersionConflict(AppError):
    def __init__(self, current: Any) -> None:
        super().__init__(
            status=409,
            code="VERSION_CONFLICT",
            message="This task was changed by another user.",
            details={"current": current},
        )

def rate_limited(message: str = "Too many requests, please try again later.") -> AppError:
    return AppError(429, "RATE_LIMITED", message)

def internal_error(message: str = "Internal server error") -> AppError:
    return AppError(500, "INTERNAL", message)
