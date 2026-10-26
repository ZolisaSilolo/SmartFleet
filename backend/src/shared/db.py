import os
from decimal import Decimal
from typing import Any

import boto3

_dynamodb_resource = None


def get_dynamodb_resource():
    """Singleton DynamoDB resource. Region comes from the Lambda runtime (AWS_REGION)."""
    global _dynamodb_resource
    if _dynamodb_resource is None:
        region_name = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        _dynamodb_resource = boto3.resource("dynamodb", region_name=region_name)
    return _dynamodb_resource


def get_table(env_var_name: str):
    """Resolve a table from its environment variable. There are deliberately no default names:
    a missing variable is a deployment error and must fail loudly."""
    table_name = os.environ.get(env_var_name)
    if not table_name:
        raise ValueError(f"Environment variable '{env_var_name}' is not set.")
    return get_dynamodb_resource().Table(table_name)


def get_client():
    """Low-level client that accepts native Python types (used for transactions)."""
    return get_dynamodb_resource().meta.client


def serialize_to_dynamodb(obj: Any) -> Any:
    """Recursively convert float to Decimal (DynamoDB has no float) and drop None values."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: serialize_to_dynamodb(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [serialize_to_dynamodb(item) for item in obj]
    if isinstance(obj, set):
        return {serialize_to_dynamodb(item) for item in obj}
    return obj


def deserialize_from_dynamodb(obj: Any) -> Any:
    """Recursively convert Decimal to int/float."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: deserialize_from_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deserialize_from_dynamodb(item) for item in obj]
    if isinstance(obj, set):
        return {deserialize_from_dynamodb(item) for item in obj}
    return obj
