"""
Per-tenant fixed-window rate limiter backed by DynamoDB (WA H4 denial-of-wallet protection for AI endpoints).
Items expire via TTL on `expiresAt`. The increment is atomic, so concurrent Lambdas share one counter.
"""
import os
import time
from typing import Optional

from botocore.exceptions import ClientError
from shared.db import get_table
from shared.errors import ApiError

WINDOWS = (("minute", 60), ("day", 86400))


def _limit(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def check_rate_limit(tenant_id: str, scope: str, now: Optional[float] = None) -> None:
    """Raise ApiError(429) when the tenant exceeded the per-minute or per-day quota for `scope`."""
    now = now if now is not None else time.time()
    table = get_table("RATE_LIMIT_TABLE")
    limits = {"minute": _limit("AI_RATE_LIMIT_PER_MINUTE", 10), "day": _limit("AI_RATE_LIMIT_PER_DAY", 300)}
    for window, seconds in WINDOWS:
        bucket = int(now // seconds)
        try:
            resp = table.update_item(
                Key={"rateKey": f"{tenant_id}#{scope}#{window}#{bucket}"},
                UpdateExpression="ADD hits :one SET expiresAt = :exp",
                ExpressionAttributeValues={":one": 1, ":exp": int((bucket + 2) * seconds)},
                ReturnValues="UPDATED_NEW",
            )
        except ClientError as exc:
            # Fail closed: if we cannot meter, we must not expose an unmetered paid API.
            raise ApiError(503, "RATE_LIMITER_UNAVAILABLE", "Request metering is unavailable, please retry") from exc
        hits = int(resp["Attributes"]["hits"])
        if hits > limits[window]:
            retry_after = int(seconds - (now % seconds)) + 1
            raise ApiError(
                429,
                "RATE_LIMITED",
                f"AI request limit reached for this {window}.",
                headers={"Retry-After": str(retry_after)},
            )
