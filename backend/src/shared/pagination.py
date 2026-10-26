"""
Tenant-scoped, paginated DynamoDB queries (WA H3).

* `paged_query`  - for API list endpoints: returns one page and an opaque `nextToken`.
* `query_all`    - for analytics: follows every page but raises instead of silently truncating
                   when the result would exceed a hard safety cap.
Every query is pinned to `tenantId = :tenant`; cursors are validated to belong to that tenant.
"""
import base64
import json
from typing import Any, Dict, List, Optional, Tuple

from boto3.dynamodb.conditions import ConditionBase, Key
from botocore.exceptions import ClientError
from shared.db import deserialize_from_dynamodb
from shared.errors import ApiError

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200
MAX_ANALYTICS_ITEMS = 20000


def encode_cursor(key: Optional[Dict[str, Any]]) -> Optional[str]:
    if not key:
        return None
    raw = json.dumps(deserialize_from_dynamodb(key), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(token: Optional[str], tenant_id: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        padded = token + "=" * (-len(token) % 4)
        key = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if not isinstance(key, dict) or key.get("tenantId") != tenant_id:
            raise ValueError("cursor tenant mismatch")
        return key
    except Exception as exc:  # malformed or foreign cursor
        raise ApiError(400, "INVALID_CURSOR", "Invalid nextToken") from exc


def parse_limit(raw: Optional[str]) -> int:
    if raw is None or raw == "":
        return DEFAULT_PAGE_SIZE
    try:
        value = int(raw)
    except ValueError as exc:
        raise ApiError(400, "INVALID_LIMIT", "limit must be an integer") from exc
    if value < 1 or value > MAX_PAGE_SIZE:
        raise ApiError(400, "INVALID_LIMIT", f"limit must be between 1 and {MAX_PAGE_SIZE}")
    return value


def _base_kwargs(
    tenant_id: str,
    range_condition: Optional[ConditionBase],
    index_name: Optional[str],
    filter_expression: Optional[ConditionBase],
    projection: Optional[str],
    names: Optional[Dict[str, str]],
    forward: bool,
    partition_attr: str,
    partition_value: Optional[str],
) -> Dict[str, Any]:
    pk = Key(partition_attr).eq(partition_value if partition_value is not None else tenant_id)
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": pk & range_condition if range_condition is not None else pk,
        "ScanIndexForward": forward,
    }
    if index_name:
        kwargs["IndexName"] = index_name
    if filter_expression is not None:
        kwargs["FilterExpression"] = filter_expression
    if projection:
        kwargs["ProjectionExpression"] = projection
    if names:
        kwargs["ExpressionAttributeNames"] = names
    return kwargs


def _query(table, request: Dict[str, Any], has_cursor: bool) -> Dict[str, Any]:
    """Run a query; a tampered cursor (valid tenant, wrong index key) is a client error, not a 500."""
    try:
        return table.query(**request)
    except ClientError as exc:
        if has_cursor and exc.response.get("Error", {}).get("Code") == "ValidationException":
            raise ApiError(400, "INVALID_CURSOR", "Invalid nextToken") from exc
        raise


def paged_query(
    table,
    tenant_id: str,
    *,
    limit: int,
    cursor: Optional[str] = None,
    index_name: Optional[str] = None,
    range_condition: Optional[ConditionBase] = None,
    filter_expression: Optional[ConditionBase] = None,
    projection: Optional[str] = None,
    names: Optional[Dict[str, str]] = None,
    forward: bool = True,
    partition_attr: str = "tenantId",
    partition_value: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return (items, nextToken). Loops until `limit` filtered items are collected or data is exhausted."""
    kwargs = _base_kwargs(
        tenant_id, range_condition, index_name, filter_expression, projection, names, forward, partition_attr, partition_value
    )
    start_key = decode_cursor(cursor, tenant_id)
    items: List[Dict[str, Any]] = []
    last_key: Optional[Dict[str, Any]] = start_key
    while True:
        remaining = limit - len(items)
        request = dict(kwargs, Limit=remaining)
        if last_key:
            request["ExclusiveStartKey"] = last_key
        resp = _query(table, request, bool(start_key))
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if len(items) >= limit or not last_key:
            break
    return deserialize_from_dynamodb(items), encode_cursor(last_key if last_key else None)


def query_all(
    table,
    tenant_id: str,
    *,
    index_name: Optional[str] = None,
    range_condition: Optional[ConditionBase] = None,
    filter_expression: Optional[ConditionBase] = None,
    projection: Optional[str] = None,
    names: Optional[Dict[str, str]] = None,
    forward: bool = True,
    partition_attr: str = "tenantId",
    partition_value: Optional[str] = None,
    max_items: int = MAX_ANALYTICS_ITEMS,
) -> List[Dict[str, Any]]:
    kwargs = _base_kwargs(
        tenant_id, range_condition, index_name, filter_expression, projection, names, forward, partition_attr, partition_value
    )
    items: List[Dict[str, Any]] = []
    last_key: Optional[Dict[str, Any]] = None
    while True:
        request = dict(kwargs)
        if last_key:
            request["ExclusiveStartKey"] = last_key
        resp = table.query(**request)
        items.extend(resp.get("Items", []))
        if len(items) > max_items:
            raise ApiError(
                422,
                "DATASET_TOO_LARGE",
                "The dataset for this request is too large to analyse. Reduce the analysis window.",
            )
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    return deserialize_from_dynamodb(items)
