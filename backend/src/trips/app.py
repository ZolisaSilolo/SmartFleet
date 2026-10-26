"""
Trip lifecycle. Dispatch and completion are single DynamoDB TRANSACTIONS across the trip, the vehicle and the
driver, so double-dispatch, double-completion and half-applied state are impossible (WA H2).
The vehicle odometer is updated asynchronously by the stream processor (events/processor.py) - single owner.
"""
from boto3.dynamodb.conditions import Attr
from shared.db import get_table, serialize_to_dynamodb
from shared.errors import ApiError, conflict
from shared.http import create_app, make_handler, parse_body, query_param, tenant
from shared.observability import metrics
from shared.pagination import paged_query, parse_limit
from shared.repo import TenantRepo, transact
from shared.response import ok
from shared.utils import current_iso_date, current_iso_time, generate_uuid
from shared.validation import check_path_id
from trips.models import CreateTripRequest, EndTripRequest

app = create_app()
trips = TenantRepo("TRIPS_TABLE", "tripId", "Trip")
vehicles = TenantRepo("VEHICLES_TABLE", "vehicleId", "Vehicle")
drivers = TenantRepo("DRIVERS_TABLE", "driverId", "Driver")


def _name(env: str) -> str:
    return get_table(env).name


@app.post("/trips")
def create_trip():
    tenant_id = tenant(app)
    req = parse_body(app, CreateTripRequest)

    vehicle = vehicles.get_optional(tenant_id, req.vehicleId)
    if not vehicle:
        raise ApiError(404, "NOT_FOUND", f"Vehicle '{req.vehicleId}' not found")
    driver = drivers.get_optional(tenant_id, req.driverId)
    if not driver:
        raise ApiError(404, "NOT_FOUND", f"Driver '{req.driverId}' not found")

    today = current_iso_date()
    if vehicle.get("status") != "ACTIVE" or vehicle.get("activeTripId"):
        raise conflict("Vehicle is not available for dispatch", "VEHICLE_UNAVAILABLE")
    if driver.get("status") != "AVAILABLE" or driver.get("activeTripId"):
        raise conflict("Driver is not available for dispatch", "DRIVER_UNAVAILABLE")
    if driver.get("licenseExpiryDate", "") < today:
        raise ApiError(409, "LICENCE_EXPIRED", "Driver's licence has expired")
    if driver.get("prdpExpiryDate") and driver["prdpExpiryDate"] < today:
        raise ApiError(409, "PRDP_EXPIRED", "Driver's PrDP has expired")
    if req.startOdometerKm < float(vehicle.get("currentOdometerKm", 0.0)):
        raise ApiError(422, "ODOMETER_REGRESSION", "startOdometerKm is below the vehicle's recorded odometer")

    now = current_iso_time()
    trip_id = generate_uuid()
    item = {
        "tenantId": tenant_id, "tripId": trip_id, "vehicleId": req.vehicleId, "driverId": req.driverId,
        "origin": req.origin, "destination": req.destination, "startOdometerKm": req.startOdometerKm,
        "startTime": req.startTime or now, "revenueZar": req.revenueZar, "status": "IN_PROGRESS",
        "createdAt": now, "updatedAt": now,
    }
    transact(
        [
            {"Put": {"TableName": _name("TRIPS_TABLE"), "Item": serialize_to_dynamodb(item),
                     "ConditionExpression": "attribute_not_exists(tripId)"}},
            {"Update": {
                "TableName": _name("VEHICLES_TABLE"), "Key": {"tenantId": tenant_id, "vehicleId": req.vehicleId},
                "UpdateExpression": "SET activeTripId = :t, updatedAt = :now",
                "ConditionExpression": "#s = :active AND attribute_not_exists(activeTripId)",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {":t": trip_id, ":now": now, ":active": "ACTIVE"}}},
            {"Update": {
                "TableName": _name("DRIVERS_TABLE"), "Key": {"tenantId": tenant_id, "driverId": req.driverId},
                "UpdateExpression": "SET #s = :ontrip, activeTripId = :t, updatedAt = :now",
                "ConditionExpression": "#s = :avail AND attribute_not_exists(activeTripId)",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {":t": trip_id, ":now": now, ":ontrip": "ON_TRIP", ":avail": "AVAILABLE"}}},
        ],
        "Vehicle or driver was dispatched by another request; refresh and retry",
    )
    metrics.add_metric(name="TripsStarted", unit="Count", value=1)
    return ok(item, 201)


def _close_trip(tenant_id: str, trip: dict, new_status: str, trip_changes: dict) -> dict:
    """Atomically close a trip and release its vehicle and driver."""
    now = current_iso_time()
    sets = ["#s = :new", "updatedAt = :now"]
    names = {"#s": "status"}
    values = {":new": new_status, ":now": now, ":inprog": "IN_PROGRESS"}
    for i, (attr, value) in enumerate(trip_changes.items()):
        names[f"#c{i}"] = attr
        values[f":c{i}"] = serialize_to_dynamodb(value)
        sets.append(f"#c{i} = :c{i}")
    transact(
        [
            {"Update": {
                "TableName": _name("TRIPS_TABLE"), "Key": {"tenantId": tenant_id, "tripId": trip["tripId"]},
                "UpdateExpression": "SET " + ", ".join(sets), "ConditionExpression": "#s = :inprog",
                "ExpressionAttributeNames": names, "ExpressionAttributeValues": values}},
            {"Update": {
                "TableName": _name("DRIVERS_TABLE"), "Key": {"tenantId": tenant_id, "driverId": trip["driverId"]},
                "UpdateExpression": "SET #s = :avail, updatedAt = :now REMOVE activeTripId",
                "ConditionExpression": "activeTripId = :t", "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {":avail": "AVAILABLE", ":now": now, ":t": trip["tripId"]}}},
            {"Update": {
                "TableName": _name("VEHICLES_TABLE"), "Key": {"tenantId": tenant_id, "vehicleId": trip["vehicleId"]},
                "UpdateExpression": "SET updatedAt = :now REMOVE activeTripId",
                "ConditionExpression": "activeTripId = :t",
                "ExpressionAttributeValues": {":now": now, ":t": trip["tripId"]}}},
        ],
        "Trip is no longer in progress",
    )
    return trips.get(tenant_id, trip["tripId"], consistent=True)


def _load_open_trip(tenant_id: str, trip_id: str) -> dict:
    trip = trips.get(tenant_id, check_path_id(trip_id, "tripId"), consistent=True)
    if trip.get("status") != "IN_PROGRESS":
        raise conflict("Trip is not in progress", "TRIP_NOT_IN_PROGRESS")
    return trip


@app.post("/trips/<trip_id>/end")
def end_trip(trip_id: str):
    tenant_id = tenant(app)
    req = parse_body(app, EndTripRequest)
    trip = _load_open_trip(tenant_id, trip_id)
    start_odo = float(trip["startOdometerKm"])
    if req.endOdometerKm < start_odo:
        raise ApiError(422, "ODOMETER_REGRESSION", f"endOdometerKm ({req.endOdometerKm}) cannot be less than startOdometerKm ({start_odo})")
    end_time = req.endTime or current_iso_time()
    if end_time < trip["startTime"]:
        raise ApiError(422, "INVALID_END_TIME", "endTime cannot be before startTime")
    changes = {"endOdometerKm": req.endOdometerKm, "distanceKm": round(req.endOdometerKm - start_odo, 2), "endTime": end_time}
    if req.revenueZar is not None:
        changes["revenueZar"] = req.revenueZar
    closed = _close_trip(tenant_id, trip, "COMPLETED", changes)
    metrics.add_metric(name="TripsCompleted", unit="Count", value=1)
    return ok(closed)


@app.post("/trips/<trip_id>/cancel")
def cancel_trip(trip_id: str):
    tenant_id = tenant(app)
    trip = _load_open_trip(tenant_id, trip_id)
    return ok(_close_trip(tenant_id, trip, "CANCELLED", {"endTime": current_iso_time()}))


@app.get("/trips")
def list_trips():
    tenant_id = tenant(app)
    vehicle_id, status = query_param(app, "vehicleId"), query_param(app, "status")
    condition = None
    if vehicle_id:
        condition = Attr("vehicleId").eq(check_path_id(vehicle_id, "vehicleId"))
    if status:
        status_cond = Attr("status").eq(status.upper())
        condition = condition & status_cond if condition is not None else status_cond
    items, token = paged_query(
        trips.table, tenant_id, limit=parse_limit(query_param(app, "limit")), cursor=query_param(app, "nextToken"),
        index_name="tenant-startTime-index", filter_expression=condition, forward=False,
    )
    return ok({"items": items, "nextToken": token})


@app.get("/trips/<trip_id>")
def get_trip(trip_id: str):
    return ok(trips.get(tenant(app), check_path_id(trip_id, "tripId")))


lambda_handler = make_handler(app)
