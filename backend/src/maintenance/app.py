"""
Maintenance workflow. Status changes that affect vehicle availability (start/finish of work) are applied in one
DynamoDB transaction with the vehicle update, so the two can never disagree (WA H2).
"""
from boto3.dynamodb.conditions import Attr
from maintenance.models import TRANSITIONS, CreateMaintenanceRequest, UpdateMaintenanceRequest
from shared.db import get_table, serialize_to_dynamodb
from shared.errors import ApiError, conflict
from shared.fleet_data import load_open_maintenance, load_vehicles
from shared.fleet_metrics import compute_overdue
from shared.http import create_app, make_handler, parse_body, query_param, tenant
from shared.pagination import paged_query, parse_limit
from shared.repo import TenantRepo, transact
from shared.response import ok
from shared.utils import current_iso_time, generate_uuid
from shared.validation import check_path_id

app = create_app()
repo = TenantRepo("MAINTENANCE_TABLE", "recordId", "Maintenance record")
vehicles = TenantRepo("VEHICLES_TABLE", "vehicleId", "Vehicle")


def _t(env: str) -> str:
    return get_table(env).name


def _vehicle_to_maintenance(tenant_id: str, vehicle_id: str, now: str) -> dict:
    return {"Update": {
        "TableName": _t("VEHICLES_TABLE"), "Key": {"tenantId": tenant_id, "vehicleId": vehicle_id},
        "UpdateExpression": "SET #s = :maint, updatedAt = :now",
        "ConditionExpression": "#s = :active AND attribute_not_exists(activeTripId)",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":maint": "IN_MAINTENANCE", ":active": "ACTIVE", ":now": now}}}


def _vehicle_to_active(tenant_id: str, vehicle_id: str, now: str) -> dict:
    return {"Update": {
        "TableName": _t("VEHICLES_TABLE"), "Key": {"tenantId": tenant_id, "vehicleId": vehicle_id},
        "UpdateExpression": "SET #s = :active, updatedAt = :now", "ConditionExpression": "#s = :maint",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":maint": "IN_MAINTENANCE", ":active": "ACTIVE", ":now": now}}}


@app.post("/maintenance")
def create_maintenance():
    tenant_id = tenant(app)
    req = parse_body(app, CreateMaintenanceRequest)
    if not vehicles.get_optional(tenant_id, req.vehicleId):
        raise ApiError(404, "NOT_FOUND", f"Vehicle '{req.vehicleId}' not found")
    now = current_iso_time()
    item = {
        "tenantId": tenant_id, "recordId": generate_uuid(), **req.model_dump(exclude_none=True),
        "costZar": round(req.costZar, 2), "createdAt": now, "updatedAt": now,
    }
    if req.status == "IN_PROGRESS":
        transact(
            [{"Put": {"TableName": _t("MAINTENANCE_TABLE"), "Item": serialize_to_dynamodb(item),
                      "ConditionExpression": "attribute_not_exists(recordId)"}},
             _vehicle_to_maintenance(tenant_id, req.vehicleId, now)],
            "Vehicle is not available for maintenance (on a trip or already in the workshop)",
        )
    else:
        repo.create(item)
    return ok(item, 201)


@app.get("/maintenance/due")
def get_maintenance_due():
    tenant_id = tenant(app)
    return ok({"items": compute_overdue(load_open_maintenance(tenant_id), load_vehicles(tenant_id))})


@app.get("/maintenance")
def list_maintenance():
    tenant_id = tenant(app)
    vehicle_id, status = query_param(app, "vehicleId"), query_param(app, "status")
    condition = None
    if vehicle_id:
        condition = Attr("vehicleId").eq(check_path_id(vehicle_id, "vehicleId"))
    if status:
        s = Attr("status").eq(status.upper())
        condition = condition & s if condition is not None else s
    items, token = paged_query(
        repo.table, tenant_id, limit=parse_limit(query_param(app, "limit")), cursor=query_param(app, "nextToken"),
        index_name="tenant-serviceDate-index", filter_expression=condition, forward=False,
    )
    return ok({"items": items, "nextToken": token})


@app.get("/maintenance/<record_id>")
def get_maintenance(record_id: str):
    return ok(repo.get(tenant(app), check_path_id(record_id, "recordId")))


@app.put("/maintenance/<record_id>")
def update_maintenance(record_id: str):
    tenant_id = tenant(app)
    check_path_id(record_id, "recordId")
    changes = parse_body(app, UpdateMaintenanceRequest).model_dump(exclude_none=True)
    if not changes:
        raise ApiError(400, "EMPTY_UPDATE", "No fields to update")
    existing = repo.get(tenant_id, record_id, consistent=True)
    old, new = existing["status"], changes.get("status", existing["status"])

    if new == old:
        changes.pop("status", None)
        return ok(repo.update(tenant_id, record_id, changes, extra_condition="#cur = :old",
                              extra_values={":old": old}, extra_names={"#cur": "status"}))
    if new not in TRANSITIONS[old]:
        raise conflict(f"Cannot change maintenance from {old} to {new}", "INVALID_TRANSITION")

    now = current_iso_time()
    changes["updatedAt"] = now
    names, values, sets = {"#s": "status"}, {":old": old}, []
    for i, (attr, value) in enumerate(changes.items()):
        names[f"#c{i}"] = attr
        values[f":c{i}"] = serialize_to_dynamodb(value)
        sets.append(f"#c{i} = :c{i}")
    ops = [{"Update": {
        "TableName": _t("MAINTENANCE_TABLE"), "Key": {"tenantId": tenant_id, "recordId": record_id},
        "UpdateExpression": "SET " + ", ".join(sets), "ConditionExpression": "#s = :old",
        "ExpressionAttributeNames": names, "ExpressionAttributeValues": values}}]
    if new == "IN_PROGRESS":
        ops.append(_vehicle_to_maintenance(tenant_id, existing["vehicleId"], now))
    elif old == "IN_PROGRESS":
        ops.append(_vehicle_to_active(tenant_id, existing["vehicleId"], now))
    transact(ops, "Maintenance changed concurrently or the vehicle is not in a valid state; refresh and retry")
    return ok(repo.get(tenant_id, record_id, consistent=True))


@app.delete("/maintenance/<record_id>")
def delete_maintenance(record_id: str):
    # Work in progress holds the vehicle in the workshop; finish or revert it first.
    repo.delete(tenant(app), check_path_id(record_id, "recordId"), guard_condition="#st <> :ip",
                guard_names={"#st": "status"}, guard_values={":ip": "IN_PROGRESS"})
    return ok({"message": "Maintenance record deleted", "recordId": record_id})


lambda_handler = make_handler(app)
