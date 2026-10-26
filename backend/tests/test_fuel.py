from datetime import UTC, datetime

from conftest import call, make_driver, make_vehicle


def _fill(fuel_h, vehicle, tenant="tenant-a", **overrides):
    body = {"vehicleId": vehicle["vehicleId"], "fillDate": "2026-01-10T08:00:00+00:00", "litres": 80, "totalCostZar": 1800,
            "odometerKm": 1500, "latitude": -28.2713, "longitude": 29.1352, "stationName": "Shell Harrismith"}
    body.update(overrides)
    return call(fuel_h, "POST", "/fuel", tenant=tenant, body=body)


def test_prices_are_never_assumed(fuel_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    status, body = _fill(fuel_h, v, totalCostZar=None)
    assert status == 400 and "never assumed" in json_text(body)
    assert _fill(fuel_h, v, totalCostZar=1000, costPerLitreZar=5)[0] == 400  # inconsistent price inputs


def json_text(body):
    import json
    return json.dumps(body)


def test_location_is_required_and_totals_are_derived(fuel_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    assert _fill(fuel_h, v, latitude=None)[0] == 400
    status, log = _fill(fuel_h, v, totalCostZar=None, costPerLitreZar=23.5)
    assert status == 201 and log["totalCostZar"] == 1880.0 and log["vehicleKey"] == f"tenant-a#{v['vehicleId']}"
    status, log = _fill(fuel_h, v, totalCostZar=1800)
    assert log["costPerLitreZar"] == 22.5


def test_references_are_validated_per_tenant(fuel_h, vehicles_h, drivers_h):
    foreign = make_vehicle(vehicles_h, tenant="tenant-b")
    assert _fill(fuel_h, foreign, tenant="tenant-a")[0] == 404
    own = make_vehicle(vehicles_h)
    foreign_driver = make_driver(drivers_h, tenant="tenant-b")
    assert _fill(fuel_h, own, driverId=foreign_driver["driverId"])[0] == 404


def test_list_newest_first_vehicle_filter_and_isolation(fuel_h, vehicles_h):
    a, b = make_vehicle(vehicles_h, plate="CA 1"), make_vehicle(vehicles_h, plate="CA 2")
    _fill(fuel_h, a, fillDate="2026-01-01T00:00:00+00:00")
    _fill(fuel_h, a, fillDate="2026-02-01T00:00:00+00:00", odometerKm=2000)
    _fill(fuel_h, b, fillDate="2026-03-01T00:00:00+00:00")
    items = call(fuel_h, "GET", "/fuel")[1]["items"]
    assert [i["fillDate"][:7] for i in items] == ["2026-03", "2026-02", "2026-01"]
    only_a = call(fuel_h, "GET", "/fuel", query={"vehicleId": a["vehicleId"]})[1]["items"]
    assert [i["fillDate"][:7] for i in only_a] == ["2026-02", "2026-01"]
    assert call(fuel_h, "GET", "/fuel", tenant="tenant-b")[1]["items"] == []
    # another tenant asking for this vehicle's logs sees nothing (vehicle key is tenant-scoped)
    assert call(fuel_h, "GET", "/fuel", tenant="tenant-b", query={"vehicleId": a["vehicleId"]})[1]["items"] == []


def test_summary_is_strictly_month_to_date(fuel_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    _fill(fuel_h, v, fillDate="2020-01-01T00:00:00+00:00")  # old data must not leak into MTD
    assert call(fuel_h, "GET", "/fuel/summary")[1]["totalLogs"] == 0
    now = datetime.now(UTC).isoformat()
    _fill(fuel_h, v, fillDate=now, litres=50, totalCostZar=1000)
    summary = call(fuel_h, "GET", "/fuel/summary")[1]
    assert summary["totalLogs"] == 1 and summary["totalLitres"] == 50 and summary["avgCostPerLitreZar"] == 20.0


def test_delete_fuel_log(fuel_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    log = _fill(fuel_h, v)[1]
    assert call(fuel_h, "DELETE", f"/fuel/{log['logId']}", tenant="tenant-b")[0] == 404
    assert call(fuel_h, "DELETE", f"/fuel/{log['logId']}")[0] == 200
    assert call(fuel_h, "GET", f"/fuel/{log['logId']}")[0] == 404
