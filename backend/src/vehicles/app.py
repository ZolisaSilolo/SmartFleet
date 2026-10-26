from boto3.dynamodb.conditions import Attr, Key
from shared.db import get_table
from shared.errors import conflict
from shared.http import create_app, make_handler, parse_body, query_param, tenant
from shared.pagination import paged_query, parse_limit
from shared.repo import TenantRepo
from shared.response import ok
from shared.utils import current_iso_time, generate_uuid
from shared.validation import check_path_id
from vehicles.models import CreateVehicleRequest, UpdateVehicleRequest

app = create_app()
repo = TenantRepo("VEHICLES_TABLE", "vehicleId", "Vehicle")


def _plate_exists(tenant_id: str, plate: str, exclude_id: str = "") -> bool:
    resp = get_table("VEHICLES_TABLE").query(
        IndexName="plate-index",
        KeyConditionExpression=Key("tenantId").eq(tenant_id) & Key("plateNumber").eq(plate),
        Limit=2,
    )
    return any(i["vehicleId"] != exclude_id for i in resp.get("Items", []))


@app.post("/vehicles")
def create_vehicle():
    tenant_id = tenant(app)
    req = parse_body(app, CreateVehicleRequest)
    plate = req.plateNumber.upper()
    if _plate_exists(tenant_id, plate):
        raise conflict(f"A vehicle with plate '{plate}' already exists", "PLATE_EXISTS")
    now = current_iso_time()
    item = {
        "tenantId": tenant_id, "vehicleId": generate_uuid(), "plateNumber": plate, "make": req.make, "model": req.model,
        "year": req.year, "fuelType": req.fuelType, "currentOdometerKm": req.currentOdometerKm,
        "targetEfficiencyLPer100Km": req.targetEfficiencyLPer100Km, "status": "ACTIVE", "createdAt": now, "updatedAt": now,
    }
    return ok(repo.create(item), 201)


@app.get("/vehicles")
def list_vehicles():
    tenant_id = tenant(app)
    status = query_param(app, "status")
    items, token = paged_query(
        repo.table, tenant_id, limit=parse_limit(query_param(app, "limit")), cursor=query_param(app, "nextToken"),
        filter_expression=Attr("status").eq(status.upper()) if status else None,
    )
    return ok({"items": items, "nextToken": token})


@app.get("/vehicles/<vehicle_id>")
def get_vehicle(vehicle_id: str):
    return ok(repo.get(tenant(app), check_path_id(vehicle_id, "vehicleId")))


@app.put("/vehicles/<vehicle_id>")
def update_vehicle(vehicle_id: str):
    tenant_id = tenant(app)
    check_path_id(vehicle_id, "vehicleId")
    changes = parse_body(app, UpdateVehicleRequest).model_dump(exclude_none=True)
    if "plateNumber" in changes:
        changes["plateNumber"] = changes["plateNumber"].upper()
        if _plate_exists(tenant_id, changes["plateNumber"], exclude_id=vehicle_id):
            raise conflict(f"A vehicle with plate '{changes['plateNumber']}' already exists", "PLATE_EXISTS")
    extra, values, names = None, None, None
    if "status" in changes:
        # A vehicle cannot be manually (de)activated while out on a trip or in the workshop.
        extra = "attribute_not_exists(activeTripId) AND #cur <> :inmaint"
        values, names = {":inmaint": "IN_MAINTENANCE"}, {"#cur": "status"}
    return ok(repo.update(tenant_id, vehicle_id, changes, extra_condition=extra, extra_values=values, extra_names=names))


@app.delete("/vehicles/<vehicle_id>")
def delete_vehicle(vehicle_id: str):
    tenant_id = tenant(app)
    repo.delete(tenant_id, check_path_id(vehicle_id, "vehicleId"), guard_condition="attribute_not_exists(activeTripId)")
    return ok({"message": "Vehicle deleted", "vehicleId": vehicle_id})


lambda_handler = make_handler(app)
