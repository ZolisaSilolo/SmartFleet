from boto3.dynamodb.conditions import Key
from fuel.models import CreateFuelRequest
from shared.errors import ApiError
from shared.http import create_app, make_handler, parse_body, query_param, tenant
from shared.pagination import paged_query, parse_limit, query_all
from shared.repo import TenantRepo
from shared.response import ok
from shared.utils import current_iso_time, generate_uuid, month_start_iso
from shared.validation import check_path_id

app = create_app()
fuel = TenantRepo("FUEL_TABLE", "logId", "Fuel log")
vehicles = TenantRepo("VEHICLES_TABLE", "vehicleId", "Vehicle")
drivers = TenantRepo("DRIVERS_TABLE", "driverId", "Driver")


@app.post("/fuel")
def log_fuel():
    tenant_id = tenant(app)
    req = parse_body(app, CreateFuelRequest)
    if not vehicles.get_optional(tenant_id, req.vehicleId):
        raise ApiError(404, "NOT_FOUND", f"Vehicle '{req.vehicleId}' not found")
    if req.driverId and not drivers.get_optional(tenant_id, req.driverId):
        raise ApiError(404, "NOT_FOUND", f"Driver '{req.driverId}' not found")

    total = req.totalCostZar if req.totalCostZar is not None else round(req.litres * req.costPerLitreZar, 2)
    per_litre = req.costPerLitreZar if req.costPerLitreZar is not None else round(total / req.litres, 4)
    now = current_iso_time()
    item = {
        "tenantId": tenant_id, "logId": generate_uuid(), "vehicleId": req.vehicleId,
        # Tenant-scoped vehicle key: the vehicle GSI can never return another tenant's rows.
        "vehicleKey": f"{tenant_id}#{req.vehicleId}",
        "driverId": req.driverId, "fillDate": req.fillDate, "litres": round(req.litres, 2),
        "costPerLitreZar": round(per_litre, 4), "totalCostZar": round(total, 2), "odometerKm": req.odometerKm,
        "fullTank": req.fullTank, "stationName": req.stationName, "latitude": req.latitude, "longitude": req.longitude,
        "createdAt": now, "updatedAt": now,
    }
    return ok(fuel.create(item), 201)


@app.get("/fuel/summary")
def get_fuel_summary():
    tenant_id = tenant(app)
    start = month_start_iso()
    items = query_all(fuel.table, tenant_id, index_name="tenant-fillDate-index", range_condition=Key("fillDate").gte(start),
                      projection="litres, totalCostZar")
    litres = sum(float(i.get("litres", 0)) for i in items)
    cost = sum(float(i.get("totalCostZar", 0)) for i in items)
    return ok({
        "period": "MTD", "periodStart": start, "totalLogs": len(items), "totalLitres": round(litres, 2),
        "totalCostZar": round(cost, 2), "avgCostPerLitreZar": round(cost / litres, 2) if litres > 0 else 0.0,
    })


@app.get("/fuel")
def list_fuel():
    tenant_id = tenant(app)
    vehicle_id = query_param(app, "vehicleId")
    limit, cursor = parse_limit(query_param(app, "limit")), query_param(app, "nextToken")
    if vehicle_id:
        items, token = paged_query(
            fuel.table, tenant_id, limit=limit, cursor=cursor, index_name="vehicle-fillDate-index", forward=False,
            partition_attr="vehicleKey", partition_value=f"{tenant_id}#{check_path_id(vehicle_id, 'vehicleId')}",
        )
    else:
        items, token = paged_query(fuel.table, tenant_id, limit=limit, cursor=cursor, index_name="tenant-fillDate-index", forward=False)
    return ok({"items": items, "nextToken": token})


@app.get("/fuel/<log_id>")
def get_fuel_log(log_id: str):
    return ok(fuel.get(tenant(app), check_path_id(log_id, "logId")))


@app.delete("/fuel/<log_id>")
def delete_fuel_log(log_id: str):
    fuel.delete(tenant(app), check_path_id(log_id, "logId"))
    return ok({"message": "Fuel log deleted", "logId": log_id})


lambda_handler = make_handler(app)
