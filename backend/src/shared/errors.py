"""Typed API errors. Raised anywhere in a request path; rendered by shared.http."""
from typing import Any, Dict, Optional


class ApiError(Exception):
    """An expected, client-visible failure with a stable machine-readable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}


def not_found(label: str, identifier: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{label} '{identifier}' not found")


def conflict(message: str, code: str = "CONFLICT") -> ApiError:
    return ApiError(409, code, message)
