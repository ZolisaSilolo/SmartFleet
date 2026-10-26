from boto3.dynamodb.conditions import Attr
from drivers.models import CreateDriverRequest, UpdateDriverRequest
from shared.errors import ApiError
from shared.http import create_app, make_handler, parse_body, query_param, tenant
from shared.pagination import paged_query, parse_limit
from shared.repo import TenantRepo
from shared.response import ok
from shared.utils import current_iso_time, generate_uuid
from shared.validation import check_path_id

app = create_app()
repo = TenantRepo("DRIVERS_TABLE", "driverId", "Driver")
vehicles = TenantRepo("VEHICLES_TABLE", "vehicleId", "Vehicle")


def _require_vehicle(tenant_id: str, vehicle_id: str) -> None:
    if not vehicles.get_optional(tenant_id, vehicle_id):
        raise ApiError(404, "NOT_FOUND", f"Vehicle '{vehicle_id}' not found")


@app.post("/drivers")
def create_driver():
    tenant_id = tenant(app)
    req = parse_body(app, CreateDriverRequest)
    if req.assignedVehicleId:
        _require_vehicle(tenant_id, req.assignedVehicleId)
    now = current_iso_time()
    item = {
        "tenantId": tenant_id, "driverId": generate_uuid(), "fullName": req.fullName, "phone": req.phone,
        "licenseNumber": req.licenseNumber.upper(), "licenseExpiryDate": req.licenseExpiryDate,
        "prdpExpiryDate": req.prdpExpiryDate, "assignedVehicleId": req.assignedVehicleId,
        "status": "AVAILABLE", "createdAt": now, "updatedAt": now,
    }
    return ok(repo.create(item), 201)


@app.get("/drivers")
def list_drivers():
    tenant_id = tenant(app)
    status = query_param(app, "status")
    items, token = paged_query(
        repo.table, tenant_id, limit=parse_limit(query_param(app, "limit")), cursor=query_param(app, "nextToken"),
        filter_expression=Attr("status").eq(status.upper()) if status else None,
    )
    return ok({"items": items, "nextToken": token})


@app.get("/drivers/<driver_id>")
def get_driver(driver_id: str):
    return ok(repo.get(tenant(app), check_path_id(driver_id, "driverId")))


@app.put("/drivers/<driver_id>")
def update_driver(driver_id: str):
    tenant_id = tenant(app)
    check_path_id(driver_id, "driverId")
    changes = parse_body(app, UpdateDriverRequest).model_dump(exclude_none=True)
    if "licenseNumber" in changes:
        changes["licenseNumber"] = changes["licenseNumber"].upper()
    if "assignedVehicleId" in changes:
        _require_vehicle(tenant_id, changes["assignedVehicleId"])
    extra, values, names = None, None, None
    if "status" in changes:
        extra = "attribute_not_exists(activeTripId)"  # status of a driver on a trip is owned by the trip workflow
    return ok(repo.update(tenant_id, driver_id, changes, extra_condition=extra, extra_values=values, extra_names=names))


@app.delete("/drivers/<driver_id>")
def delete_driver(driver_id: str):
    tenant_id = tenant(app)
    repo.delete(tenant_id, check_path_id(driver_id, "driverId"), guard_condition="attribute_not_exists(activeTripId)")
    return ok({"message": "Driver deleted", "driverId": driver_id})


lambda_handler = make_handler(app)
