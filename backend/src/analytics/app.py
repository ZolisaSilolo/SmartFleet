"""Read-only analytics. All data is tenant-scoped, paginated and limited to the analysis window (see fleet_data)."""
from pydantic import Field
from shared.corridors import list_reference_data, plan_route
from shared.fleet_data import load_fleet, load_stations
from shared.fleet_metrics import compute_costs, compute_dashboard, compute_efficiency, compute_utilisation
from shared.geo import check_against_stations
from shared.http import create_app, make_handler, parse_body, tenant
from shared.response import ok
from shared.validation import RequestModel

app = create_app()


class PlanRouteRequest(RequestModel):
    originHub: str = Field(..., min_length=2, max_length=60)
    destinationHub: str = Field(..., min_length=2, max_length=60)


class VerifyFuelRequest(RequestModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


@app.get("/analytics/dashboard")
def get_dashboard():
    return ok(compute_dashboard(load_fleet(tenant(app))))


@app.get("/analytics/costs")
def get_costs():
    data = load_fleet(tenant(app), include_drivers=False)
    return ok({"windowDays": data.window_days, "items": compute_costs(data)})


@app.get("/analytics/efficiency")
def get_efficiency():
    data = load_fleet(tenant(app), include_drivers=False)
    return ok({"windowDays": data.window_days, "items": compute_efficiency(data)})


@app.get("/analytics/utilisation")
def get_utilisation():
    data = load_fleet(tenant(app), include_drivers=False)
    return ok({"windowDays": 30, "items": compute_utilisation(data)})


@app.get("/analytics/corridors")
def get_corridors():
    tenant(app)  # authenticated tenants only
    return ok(list_reference_data())


@app.post("/analytics/plan-route")
def post_plan_route():
    tenant(app)
    req = parse_body(app, PlanRouteRequest)
    return ok(plan_route(req.originHub, req.destinationHub))


@app.post("/analytics/verify-fuel-location")
def verify_fuel_location():
    tenant_id = tenant(app)
    req = parse_body(app, VerifyFuelRequest)
    return ok(check_against_stations(req.latitude, req.longitude, load_stations(tenant_id)))


lambda_handler = make_handler(app)
