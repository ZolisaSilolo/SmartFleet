
from conftest import call, make_driver, make_vehicle


def _setup(vehicles_h, drivers_h, tenant="tenant-a", odometer=1000.0, **driver_kwargs):
    return make_vehicle(vehicles_h, tenant=tenant, odometer=odometer), make_driver(drivers_h, tenant=tenant, **driver_kwargs)


def _start(trips_h, v, d, tenant="tenant-a", odo=1000.0):
    return call(trips_h, "POST", "/trips", tenant=tenant, body={
        "vehicleId": v["vehicleId"], "driverId": d["driverId"], "origin": "Johannesburg", "destination": "Durban",
        "startOdometerKm": odo, "revenueZar": 15000})


def test_dispatch_is_atomic_and_locks_vehicle_and_driver(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    status, trip = _start(trips_h, v, d)
    assert status == 201 and trip["status"] == "IN_PROGRESS"
    assert call(drivers_h, "GET", f"/drivers/{d['driverId']}")[1]["status"] == "ON_TRIP"
    assert call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[1]["activeTripId"] == trip["tripId"]


def test_cannot_double_dispatch_vehicle_or_driver(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    assert _start(trips_h, v, d)[0] == 201
    other_driver = make_driver(drivers_h)
    status, body = _start(trips_h, v, other_driver)
    assert status == 409 and body["error"]["code"] == "VEHICLE_UNAVAILABLE"
    other_vehicle = make_vehicle(vehicles_h, plate="CA 999-999")
    status, body = _start(trips_h, other_vehicle, d)
    assert status == 409 and body["error"]["code"] == "DRIVER_UNAVAILABLE"


def test_dispatch_business_rules(trips_h, vehicles_h, drivers_h):
    v, expired = _setup(vehicles_h, drivers_h, license_expiry="2020-01-01")
    status, body = _start(trips_h, v, expired)
    assert status == 409 and body["error"]["code"] == "LICENCE_EXPIRED"
    ok_driver = make_driver(drivers_h)
    assert _start(trips_h, v, ok_driver, odo=10)[1]["error"]["code"] == "ODOMETER_REGRESSION"
    inactive = make_vehicle(vehicles_h, plate="CA 5")
    call(vehicles_h, "PUT", f"/vehicles/{inactive['vehicleId']}", body={"status": "INACTIVE"})
    assert _start(trips_h, inactive, ok_driver)[1]["error"]["code"] == "VEHICLE_UNAVAILABLE"
    assert call(trips_h, "POST", "/trips", body={"vehicleId": "nope", "driverId": ok_driver["driverId"], "origin": "AA", "destination": "BB", "startOdometerKm": 1})[0] == 404


def test_cannot_dispatch_with_another_tenants_vehicle_or_driver(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h, tenant="tenant-b")
    assert _start(trips_h, v, d, tenant="tenant-a")[0] == 404
    assert call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}", tenant="tenant-b")[1].get("activeTripId") is None


def test_end_trip_releases_resources_and_cannot_be_ended_twice(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    trip = _start(trips_h, v, d)[1]
    status, done = call(trips_h, "POST", f"/trips/{trip['tripId']}/end", body={"endOdometerKm": 1568, "revenueZar": 16000})
    assert status == 200 and done["status"] == "COMPLETED" and done["distanceKm"] == 568 and done["revenueZar"] == 16000
    assert call(drivers_h, "GET", f"/drivers/{d['driverId']}")[1]["status"] == "AVAILABLE"
    assert "activeTripId" not in call(drivers_h, "GET", f"/drivers/{d['driverId']}")[1]
    assert "activeTripId" not in call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[1]
    status, body = call(trips_h, "POST", f"/trips/{trip['tripId']}/end", body={"endOdometerKm": 9999})
    assert status == 409 and body["error"]["code"] == "TRIP_NOT_IN_PROGRESS"
    assert _start(trips_h, v, d, odo=1568)[0] == 201  # resources are reusable


def test_end_trip_validation_and_isolation(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    trip = _start(trips_h, v, d)[1]
    assert call(trips_h, "POST", f"/trips/{trip['tripId']}/end", body={"endOdometerKm": 5})[1]["error"]["code"] == "ODOMETER_REGRESSION"
    assert call(trips_h, "POST", f"/trips/{trip['tripId']}/end", tenant="tenant-b", body={"endOdometerKm": 2000})[0] == 404
    assert call(trips_h, "POST", f"/trips/{trip['tripId']}/end", body={"endOdometerKm": 2000, "tenantId": "x"})[0] == 400
    assert call(trips_h, "POST", f"/trips/{trip['tripId']}/end", body={"endOdometerKm": 2000, "endTime": "2000-01-01T00:00:00Z"})[1]["error"]["code"] == "INVALID_END_TIME"


def test_cancel_releases_resources(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    trip = _start(trips_h, v, d)[1]
    status, body = call(trips_h, "POST", f"/trips/{trip['tripId']}/cancel")
    assert status == 200 and body["status"] == "CANCELLED"
    assert call(drivers_h, "GET", f"/drivers/{d['driverId']}")[1]["status"] == "AVAILABLE"


def test_busy_vehicle_and_driver_cannot_be_deleted(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    _start(trips_h, v, d)
    assert call(vehicles_h, "DELETE", f"/vehicles/{v['vehicleId']}")[0] == 409
    assert call(drivers_h, "DELETE", f"/drivers/{d['driverId']}")[0] == 409
    assert call(vehicles_h, "PUT", f"/vehicles/{v['vehicleId']}", body={"status": "INACTIVE"})[0] == 409


def test_list_trips_newest_first_with_filters(trips_h, vehicles_h, drivers_h):
    v, d = _setup(vehicles_h, drivers_h)
    t1 = _start(trips_h, v, d)[1]
    call(trips_h, "POST", f"/trips/{t1['tripId']}/end", body={"endOdometerKm": 1100})
    t2 = _start(trips_h, v, d, odo=1100)[1]
    items = call(trips_h, "GET", "/trips")[1]["items"]
    assert [i["tripId"] for i in items] == [t2["tripId"], t1["tripId"]]
    assert [i["tripId"] for i in call(trips_h, "GET", "/trips", query={"status": "completed"})[1]["items"]] == [t1["tripId"]]
    assert len(call(trips_h, "GET", "/trips", query={"vehicleId": v["vehicleId"], "limit": "1"})[1]["items"]) == 1
    assert call(trips_h, "GET", "/trips", tenant="tenant-b")[1]["items"] == []


def test_transaction_rejects_a_race_even_when_the_precheck_read_is_stale(trips_h, vehicles_h, drivers_h, monkeypatch):
    """The pre-checks are a UX nicety; the DynamoDB transaction conditions are what actually prevent double-dispatch."""
    import trips.app as trips_app

    v, d = _setup(vehicles_h, drivers_h)
    assert _start(trips_h, v, d)[0] == 201
    d2 = make_driver(drivers_h)
    stale_vehicle = {k: val for k, val in v.items()}  # a read taken BEFORE the first dispatch committed
    monkeypatch.setattr(trips_app.vehicles, "get_optional", lambda tenant, vid, consistent=True: stale_vehicle)
    status, body = _start(trips_h, v, d2)
    assert status == 409 and body["error"]["code"] == "CONFLICT"
    assert call(drivers_h, "GET", f"/drivers/{d2['driverId']}")[1]["status"] == "AVAILABLE"  # nothing half-applied
    assert len(call(trips_h, "GET", "/trips")[1]["items"]) == 1
