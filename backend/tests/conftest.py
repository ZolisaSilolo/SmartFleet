"""
Test harness. Tables are created FROM infrastructure/template.yaml so tests always run against the exact keys and
indexes that production deploys (no hand-copied schemas that can drift).
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Environment must be set before application modules are imported.
os.environ.update({
    "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "af-south-1", "AWS_REGION": "af-south-1",
    "POWERTOOLS_TRACE_DISABLED": "true", "POWERTOOLS_METRICS_NAMESPACE": "SmartFleetTest", "POWERTOOLS_SERVICE_NAME": "smart-fleet",
    "POWERTOOLS_LOG_LEVEL": "CRITICAL",
    "EVENT_BUS_NAME": "test-bus", "BEDROCK_MODEL_ID": "global.test-model", "BEDROCK_SUPPORTS_TEMPERATURE": "false", "AI_ENABLED": "true",
    "AI_RATE_LIMIT_PER_MINUTE": "3", "AI_RATE_LIMIT_PER_DAY": "50", "ANALYTICS_LOOKBACK_DAYS": "365",
    "FUEL_ANOMALY_THRESHOLD_PCT": "15", "STAGE": "test",
})

import boto3  # noqa: E402
import pytest  # noqa: E402
import yaml  # noqa: E402
from moto import mock_aws  # noqa: E402

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "infrastructure" / "template.yaml"
TABLE_ENV = {
    "VehiclesTable": "VEHICLES_TABLE", "DriversTable": "DRIVERS_TABLE", "TripsTable": "TRIPS_TABLE", "FuelTable": "FUEL_TABLE",
    "MaintenanceTable": "MAINTENANCE_TABLE", "StationsTable": "STATIONS_TABLE", "RateLimitTable": "RATE_LIMIT_TABLE",
}
for _logical, _env in TABLE_ENV.items():
    os.environ[_env] = f"test-{_logical}"


class CfnLoader(yaml.SafeLoader):
    """YAML loader that tolerates CloudFormation short-form intrinsics (!Ref, !If, ...)."""


def _intrinsic(loader: CfnLoader, tag_suffix: str, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node, deep=True)}
    return {tag_suffix: loader.construct_mapping(node, deep=True)}


CfnLoader.add_multi_constructor("!", _intrinsic)


def load_template() -> Dict[str, Any]:
    return yaml.load(TEMPLATE_PATH.read_text(encoding="utf-8"), Loader=CfnLoader)


def _create_tables() -> None:
    client = boto3.client("dynamodb", region_name="af-south-1")
    for logical, resource in load_template()["Resources"].items():
        if resource["Type"] != "AWS::DynamoDB::Table":
            continue
        props = resource["Properties"]
        kwargs: Dict[str, Any] = {
            "TableName": f"test-{logical}", "BillingMode": "PAY_PER_REQUEST",
            "AttributeDefinitions": props["AttributeDefinitions"], "KeySchema": props["KeySchema"],
        }
        if props.get("GlobalSecondaryIndexes"):
            kwargs["GlobalSecondaryIndexes"] = [
                {"IndexName": g["IndexName"], "KeySchema": g["KeySchema"], "Projection": g["Projection"]}
                for g in props["GlobalSecondaryIndexes"]
            ]
        if props.get("StreamSpecification"):
            kwargs["StreamSpecification"] = {"StreamEnabled": True, "StreamViewType": props["StreamSpecification"]["StreamViewType"]}
        client.create_table(**kwargs)


@pytest.fixture(autouse=True)
def aws():
    with mock_aws():
        import events.processor as processor
        import shared.bedrock as bedrock
        import shared.db as db

        db._dynamodb_resource = None
        bedrock._client = None
        processor._events_client = None
        _create_tables()
        boto3.client("events", region_name="af-south-1").create_event_bus(Name="test-bus")
        os.environ["AI_ENABLED"] = "true"
        yield


class FakeContext:
    function_name = "test-fn"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:af-south-1:123456789012:function:test-fn"
    aws_request_id = "req-123"

    def get_remaining_time_in_millis(self) -> int:
        return 25000


def make_event(method: str, path: str, tenant: Optional[str] = "tenant-a", body: Any = None,
               query: Optional[Dict[str, str]] = None, token_use: str = "id", sub: str = "user-1") -> Dict[str, Any]:
    """Build an API Gateway HTTP API payload-format-2.0 event exactly as the JWT authorizer produces it."""
    claims: Dict[str, str] = {"sub": sub, "token_use": token_use, "email": "user@example.test"}
    if tenant:
        claims["custom:tenantId"] = tenant
    return {
        "version": "2.0", "routeKey": f"{method} {path}", "rawPath": f"/prod{path}",
        "rawQueryString": "&".join(f"{k}={v}" for k, v in (query or {}).items()),
        "queryStringParameters": query or None,
        "headers": {"content-type": "application/json", "authorization": "Bearer redacted"},
        "requestContext": {
            "accountId": "123456789012", "apiId": "api", "domainName": "x.execute-api.af-south-1.amazonaws.com",
            "http": {"method": method, "path": f"/prod{path}", "protocol": "HTTP/1.1", "sourceIp": "203.0.113.1", "userAgent": "pytest"},
            "requestId": "r1", "routeKey": f"{method} {path}", "stage": "prod", "time": "01/Jan/2026:00:00:00 +0000", "timeEpoch": 0,
            "authorizer": {"jwt": {"claims": claims, "scopes": None}},
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def call(handler, method: str, path: str, **kwargs):
    """Invoke a Lambda handler; returns (status_code, parsed_json_body)."""
    response = handler(make_event(method, path, **kwargs), FakeContext())
    body = response.get("body")
    return response["statusCode"], (json.loads(body) if body else None)


# ---- data builders shared by tests -------------------------------------------------------------------------
def make_vehicle(handler, tenant="tenant-a", plate="CA 111-111", odometer=1000.0, target=10.0) -> Dict[str, Any]:
    status, body = call(handler, "POST", "/vehicles", tenant=tenant, body={
        "plateNumber": plate, "make": "Isuzu", "model": "NPR 400", "year": 2022, "fuelType": "DIESEL",
        "currentOdometerKm": odometer, "targetEfficiencyLPer100Km": target})
    assert status == 201, body
    return body


def make_driver(handler, tenant="tenant-a", license_expiry="2099-12-31", prdp="2099-12-31") -> Dict[str, Any]:
    status, body = call(handler, "POST", "/drivers", tenant=tenant, body={
        "fullName": "Sipho Ndlovu", "phone": "+27821234567", "licenseNumber": "abc123456",
        "licenseExpiryDate": license_expiry, "prdpExpiryDate": prdp})
    assert status == 201, body
    return body


@pytest.fixture
def vehicles_h():
    from vehicles.app import lambda_handler
    return lambda_handler


@pytest.fixture
def drivers_h():
    from drivers.app import lambda_handler
    return lambda_handler


@pytest.fixture
def trips_h():
    from trips.app import lambda_handler
    return lambda_handler


@pytest.fixture
def fuel_h():
    from fuel.app import lambda_handler
    return lambda_handler


@pytest.fixture
def maint_h():
    from maintenance.app import lambda_handler
    return lambda_handler


@pytest.fixture
def stations_h():
    from stations.app import lambda_handler
    return lambda_handler


@pytest.fixture
def analytics_h():
    from analytics.app import lambda_handler
    return lambda_handler


@pytest.fixture
def ai_h():
    from ai.app import lambda_handler
    return lambda_handler
