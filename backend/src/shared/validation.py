"""Strict request-model foundations (WA H2: reject unknown fields => no mass assignment)."""
import re
from datetime import UTC, date, datetime
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_PHONE_PATTERN = re.compile(r"^(\+27|0)\d{9}$")


class RequestModel(BaseModel):
    """Base for all inbound payloads: unknown fields are rejected, whitespace is trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def validate_resource_id(value: str) -> str:
    if not _ID_PATTERN.match(value):
        raise ValueError("must be 1-64 characters: letters, digits, '-' or '_'")
    return value


def validate_iso_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be an ISO date (YYYY-MM-DD)") from exc
    return value


def normalize_timestamp(value: str) -> str:
    """Normalise an ISO date or timestamp to a UTC ISO-8601 string so range keys sort lexicographically."""
    try:
        if len(value) == 10:
            parsed = datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            parsed = parsed.astimezone(UTC)
    except ValueError as exc:
        raise ValueError("must be an ISO-8601 date or timestamp") from exc
    return parsed.isoformat()


def validate_phone(value: str) -> str:
    if not _PHONE_PATTERN.match(value):
        raise ValueError("must be a South African number: +27XXXXXXXXX or 0XXXXXXXXX")
    return value


ResourceId = Annotated[str, AfterValidator(validate_resource_id)]
IsoDate = Annotated[str, AfterValidator(validate_iso_date)]
IsoTimestamp = Annotated[str, AfterValidator(normalize_timestamp)]
SaPhone = Annotated[str, AfterValidator(validate_phone)]
OptionalIsoDate = Optional[IsoDate]


def check_path_id(value: str, label: str = "id") -> str:
    """Validate a path parameter; raises ApiError(400) on malformed ids."""
    from shared.errors import ApiError

    if not _ID_PATTERN.match(value or ""):
        raise ApiError(400, "INVALID_ID", f"Invalid {label}.")
    return value
