"""Tenant-managed authorised fuel stations used for geofence verification of fill-ups."""
from shared.http import create_app, make_handler, parse_body, query_param, tenant
from shared.pagination import paged_query, parse_limit
from shared.repo import TenantRepo
from shared.response import ok
from shared.utils import current_iso_time, generate_uuid
from shared.validation import check_path_id
from stations.models import CreateStationRequest, UpdateStationRequest

app = create_app()
repo = TenantRepo("STATIONS_TABLE", "stationId", "Station")


@app.post("/stations")
def create_station():
    tenant_id = tenant(app)
    req = parse_body(app, CreateStationRequest)
    now = current_iso_time()
    item = {"tenantId": tenant_id, "stationId": generate_uuid(), **req.model_dump(exclude_none=True), "createdAt": now, "updatedAt": now}
    return ok(repo.create(item), 201)


@app.get("/stations")
def list_stations():
    tenant_id = tenant(app)
    items, token = paged_query(repo.table, tenant_id, limit=parse_limit(query_param(app, "limit")), cursor=query_param(app, "nextToken"))
    return ok({"items": items, "nextToken": token})


@app.put("/stations/<station_id>")
def update_station(station_id: str):
    tenant_id = tenant(app)
    changes = parse_body(app, UpdateStationRequest).model_dump(exclude_none=True)
    return ok(repo.update(tenant_id, check_path_id(station_id, "stationId"), changes))


@app.delete("/stations/<station_id>")
def delete_station(station_id: str):
    repo.delete(tenant(app), check_path_id(station_id, "stationId"))
    return ok({"message": "Station deleted", "stationId": station_id})


lambda_handler = make_handler(app)
