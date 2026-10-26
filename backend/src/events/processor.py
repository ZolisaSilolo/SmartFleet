"""
Change-data-capture worker for the Trips and Fuel streams.

Reliability contract (WA H1):
  * Errors are NEVER swallowed. Any failure is raised so Powertools reports it as a partial batch failure;
    Lambda retries, bisects, and finally ships the record to the SQS on-failure destination (alarmed).
  * Every side effect is idempotent, so retries and redelivery are safe:
      - odometer update is monotonic (conditional), so replays are no-ops;
      - EventBridge events are at-least-once; consumers must be idempotent (events carry stable ids).
Single ownership: this worker owns vehicle odometer. Trip/maintenance status effects are applied
transactionally by the APIs and are not duplicated here.
"""
import json
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import DynamoDBRecord
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from shared.db import deserialize_from_dynamodb, get_table
from shared.fleet_data import load_stations
from shared.fleet_metrics import efficiency_anomaly_pct
from shared.geo import check_against_stations
from shared.observability import logger, metrics, tracer
from shared.utils import current_iso_time

processor = BatchProcessor(event_type=EventType.DynamoDBStreams)
_deserializer = TypeDeserializer()
_events_client = None
MAX_FILLS_LOOKBACK = 50


def get_events_client():
    global _events_client
    if _events_client is None:
        _events_client = boto3.client("events", region_name=os.environ.get("AWS_REGION"))
    return _events_client


def unmarshal(image: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not image:
        return {}
    return deserialize_from_dynamodb({k: _deserializer.deserialize(v) for k, v in image.items()})


def emit_event(detail_type: str, source: str, detail: Dict[str, Any]) -> None:
    bus_name = os.environ["EVENT_BUS_NAME"]
    resp = get_events_client().put_events(
        Entries=[{"Source": source, "DetailType": detail_type, "Detail": json.dumps(detail, default=str), "EventBusName": bus_name}]
    )
    if resp.get("FailedEntryCount", 0) > 0:
        raise RuntimeError(f"EventBridge rejected {detail_type}: {resp['Entries'][0].get('ErrorCode')}")


def source_table(record: DynamoDBRecord) -> str:
    arn = record.event_source_arn or ""
    return arn.split("table/")[1].split("/")[0] if "table/" in arn else ""


def apply_trip_completed(tenant_id: str, old: Dict[str, Any], new: Dict[str, Any]) -> None:
    end_odo = new.get("endOdometerKm")
    if end_odo is not None and new.get("vehicleId"):
        try:
            get_table("VEHICLES_TABLE").update_item(
                Key={"tenantId": tenant_id, "vehicleId": new["vehicleId"]},
                UpdateExpression="SET currentOdometerKm = :odo, updatedAt = :now",
                ConditionExpression="attribute_exists(tenantId) AND (attribute_not_exists(currentOdometerKm) OR currentOdometerKm < :odo)",
                ExpressionAttributeValues={":odo": Decimal(str(end_odo)), ":now": current_iso_time()},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise  # throttling etc. must be retried - only the "already applied" case is benign
    emit_event(
        "TripCompleted", "smartfleet.trips",
        {"tenantId": tenant_id, "tripId": new["tripId"], "vehicleId": new.get("vehicleId"), "driverId": new.get("driverId"),
         "distanceKm": new.get("distanceKm"), "revenueZar": new.get("revenueZar")},
    )
    metrics.add_metric(name="TripCompletedProcessed", unit="Count", value=1)


def consumption_since_last_full_fill(tenant_id: str, fill: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Full-tank method: litres consumed between the previous FULL fill-up and this FULL fill-up."""
    if not fill.get("fullTank", True):
        return None
    table = get_table("FUEL_TABLE")
    partial_litres = 0.0
    seen = 0
    last_key = None
    while seen < MAX_FILLS_LOOKBACK:
        request = dict(
            IndexName="vehicle-fillDate-index",
            KeyConditionExpression=Key("vehicleKey").eq(f"{tenant_id}#{fill['vehicleId']}") & Key("fillDate").lt(fill["fillDate"]),
            ScanIndexForward=False,
            Limit=MAX_FILLS_LOOKBACK - seen,
        )
        if last_key:
            request["ExclusiveStartKey"] = last_key
        resp = table.query(**request)
        for prev in deserialize_from_dynamodb(resp.get("Items", [])):
            seen += 1
            if prev.get("fullTank", True):
                distance = float(fill["odometerKm"]) - float(prev["odometerKm"])
                litres = float(fill["litres"]) + partial_litres
                if distance <= 0 or litres <= 0:
                    return None
                return {"distanceKm": distance, "litres": litres, "lPer100Km": litres / distance * 100.0}
            partial_litres += float(prev["litres"])
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            return None
    return None


def apply_fuel_insert(tenant_id: str, fill: Dict[str, Any]) -> None:
    vehicle = get_table("VEHICLES_TABLE").get_item(Key={"tenantId": tenant_id, "vehicleId": fill["vehicleId"]}).get("Item")
    if vehicle:
        target = float(vehicle.get("targetEfficiencyLPer100Km", 0))
        measured = consumption_since_last_full_fill(tenant_id, fill)
        threshold = efficiency_anomaly_pct()
        if measured and target > 0 and measured["lPer100Km"] > target * (1 + threshold / 100.0):
            emit_event(
                "FuelAnomalyDetected", "smartfleet.fuel",
                {"tenantId": tenant_id, "vehicleId": fill["vehicleId"], "logId": fill["logId"],
                 "actualLPer100Km": round(measured["lPer100Km"], 2), "targetLPer100Km": target, "thresholdPercent": threshold},
            )
            metrics.add_metric(name="FuelAnomalies", unit="Count", value=1)

    stations = load_stations(tenant_id)
    check = check_against_stations(fill.get("latitude"), fill.get("longitude"), stations)
    if check["status"] == "OUTSIDE_AUTHORIZED":
        emit_event(
            "FuelOffGeofence", "smartfleet.fuel",
            {"tenantId": tenant_id, "vehicleId": fill["vehicleId"], "logId": fill["logId"],
             "nearestStation": check["stationName"], "distanceKm": check["distanceKm"], "radiusKm": check["radiusKm"]},
        )
        metrics.add_metric(name="FuelOffGeofence", unit="Count", value=1)


def record_handler(record: DynamoDBRecord) -> None:
    stream = record.raw_event.get("dynamodb", {})
    new, old = unmarshal(stream.get("NewImage")), unmarshal(stream.get("OldImage"))
    if not new or not new.get("tenantId"):
        return  # REMOVE events carry no NewImage; nothing to derive
    table = source_table(record)
    tenant_id = new["tenantId"]

    if table == os.environ["TRIPS_TABLE"]:
        if new.get("status") == "COMPLETED" and old.get("status") != "COMPLETED":
            apply_trip_completed(tenant_id, old, new)
    elif table == os.environ["FUEL_TABLE"]:
        if record.raw_event.get("eventName") == "INSERT":
            apply_fuel_insert(tenant_id, new)
    else:
        raise ValueError(f"Unexpected stream source table: {table!r}")


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return process_partial_response(event=event, record_handler=record_handler, processor=processor, context=context)
