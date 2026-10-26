"""
Tenant-scoped repository helpers. Every key includes `tenantId` taken from the verified JWT, so a caller
can never address another tenant's items (WA SEC03/SEC08). Updates are conditional (no lost updates,
no phantom items) and deletes report 404 instead of silently succeeding.
"""
from typing import Any, Dict, Iterable, List, Optional

from botocore.exceptions import ClientError
from shared.db import deserialize_from_dynamodb, get_client, get_table, serialize_to_dynamodb
from shared.errors import ApiError, conflict, not_found
from shared.utils import current_iso_time


def is_conditional_failure(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def is_transaction_canceled(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "TransactionCanceledException"


class TenantRepo:
    """CRUD for a table keyed (tenantId, <id_attr>)."""

    def __init__(self, table_env: str, id_attr: str, label: str):
        self.table_env = table_env
        self.id_attr = id_attr
        self.label = label

    @property
    def table(self):
        return get_table(self.table_env)

    def key(self, tenant_id: str, item_id: str) -> Dict[str, str]:
        return {"tenantId": tenant_id, self.id_attr: item_id}

    def create(self, item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.table.put_item(
                Item=serialize_to_dynamodb(item),
                ConditionExpression="attribute_not_exists(tenantId) AND attribute_not_exists(#id)",
                ExpressionAttributeNames={"#id": self.id_attr},
            )
        except ClientError as exc:
            if is_conditional_failure(exc):
                raise conflict(f"{self.label} already exists") from exc
            raise
        return item

    def get(self, tenant_id: str, item_id: str, consistent: bool = False) -> Dict[str, Any]:
        resp = self.table.get_item(Key=self.key(tenant_id, item_id), ConsistentRead=consistent)
        item = resp.get("Item")
        if not item:
            raise not_found(self.label, item_id)
        return deserialize_from_dynamodb(item)

    def get_optional(self, tenant_id: str, item_id: str, consistent: bool = True) -> Optional[Dict[str, Any]]:
        resp = self.table.get_item(Key=self.key(tenant_id, item_id), ConsistentRead=consistent)
        item = resp.get("Item")
        return deserialize_from_dynamodb(item) if item else None

    def update(self, tenant_id: str, item_id: str, changes: Dict[str, Any], extra_condition: Optional[str] = None,
               extra_values: Optional[Dict[str, Any]] = None, extra_names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Conditional partial update. Returns the new item; 404 if it does not exist."""
        changes = {k: v for k, v in changes.items() if v is not None}
        changes["updatedAt"] = current_iso_time()
        sets: List[str] = []
        names: Dict[str, str] = {}
        values: Dict[str, Any] = {}
        for i, (attr, value) in enumerate(changes.items()):
            names[f"#k{i}"] = attr
            values[f":v{i}"] = serialize_to_dynamodb(value)
            sets.append(f"#k{i} = :v{i}")
        condition = "attribute_exists(tenantId)"
        if extra_condition:
            condition += f" AND ({extra_condition})"
        values.update(extra_values or {})
        names.update(extra_names or {})
        try:
            resp = self.table.update_item(
                Key=self.key(tenant_id, item_id),
                UpdateExpression="SET " + ", ".join(sets),
                ConditionExpression=condition,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if is_conditional_failure(exc):
                if extra_condition and self.get_optional(tenant_id, item_id):
                    raise conflict(f"{self.label} cannot be changed in its current state") from exc
                raise not_found(self.label, item_id) from exc
            raise
        return deserialize_from_dynamodb(resp["Attributes"])

    def delete(self, tenant_id: str, item_id: str, guard_condition: Optional[str] = None,
               guard_names: Optional[Dict[str, str]] = None, guard_values: Optional[Dict[str, Any]] = None) -> None:
        condition = "attribute_exists(tenantId)"
        if guard_condition:
            condition += f" AND ({guard_condition})"
        extra: Dict[str, Any] = {}
        if guard_names:
            extra["ExpressionAttributeNames"] = guard_names
        if guard_values:
            extra["ExpressionAttributeValues"] = guard_values
        try:
            self.table.delete_item(Key=self.key(tenant_id, item_id), ConditionExpression=condition, **extra)
        except ClientError as exc:
            if is_conditional_failure(exc):
                if guard_condition and self.get_optional(tenant_id, item_id):
                    raise conflict(f"{self.label} is in use and cannot be deleted") from exc
                raise not_found(self.label, item_id) from exc
            raise


def transact(items: Iterable[Dict[str, Any]], conflict_message: str) -> None:
    """Run a DynamoDB transaction; map cancellation (failed conditions) to HTTP 409."""
    try:
        get_client().transact_write_items(TransactItems=list(items))
    except ClientError as exc:
        if is_transaction_canceled(exc):
            raise ApiError(409, "CONFLICT", conflict_message) from exc
        raise
