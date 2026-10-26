"""JSON response helpers. The API is same-origin behind CloudFront, so no CORS headers are emitted;
security headers (HSTS, CSP, ...) are applied by the CloudFront response-headers policy."""
import json
from decimal import Decimal
from typing import Any, Dict, Optional

from aws_lambda_powertools.event_handler import Response
from shared.db import deserialize_from_dynamodb


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return str(obj)


def dumps(data: Any) -> str:
    return json.dumps(deserialize_from_dynamodb(data), default=_json_default, separators=(",", ":"))


def ok(data: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> Response:
    merged = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    merged.update(headers or {})
    return Response(status_code=status_code, content_type="application/json", body=dumps(data), headers=merged)


def error(status_code: int, code: str, message: str, details: Any = None, headers: Optional[Dict[str, str]] = None) -> Response:
    payload: Dict[str, Any] = {"error": {"statusCode": status_code, "code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return ok(payload, status_code=status_code, headers=headers)
