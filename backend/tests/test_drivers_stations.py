from conftest import call, make_driver, make_vehicle


def test_driver_crud_validation_and_pii_normalisation(drivers_h):
    d = make_driver(drivers_h)
    assert d["licenseNumber"] == "ABC123456" and d["status"] == "AVAILABLE"
    assert call(drivers_h, "POST", "/drivers", body={"fullName": "X", "phone": "123"})[0] == 400
    bad_phone = {"fullName": "Thabo M", "phone": "12345", "licenseNumber": "L123", "licenseExpiryDate": "2099-01-01"}
    assert call(drivers_h, "POST", "/drivers", body=bad_phone)[0] == 400
    bad_date = {"fullName": "Thabo M", "phone": "0821234567", "licenseNumber": "L123", "licenseExpiryDate": "next year"}
    assert call(drivers_h, "POST", "/drivers", body=bad_date)[0] == 400
    status, updated = call(drivers_h, "PUT", f"/drivers/{d['driverId']}", body={"status": "OFF_DUTY"})
    assert status == 200 and updated["status"] == "OFF_DUTY"
    assert call(drivers_h, "PUT", f"/drivers/{d['driverId']}", body={"status": "ON_TRIP"})[0] == 400  # owned by trips


def test_driver_tenant_isolation_and_assigned_vehicle_ownership(drivers_h, vehicles_h):
    d = make_driver(drivers_h)
    assert call(drivers_h, "GET", f"/drivers/{d['driverId']}", tenant="tenant-b")[0] == 404
    foreign_vehicle = make_vehicle(vehicles_h, tenant="tenant-b")
    status, _ = call(drivers_h, "PUT", f"/drivers/{d['driverId']}", body={"assignedVehicleId": foreign_vehicle["vehicleId"]})
    assert status == 404  # cannot reference another tenant's vehicle


def test_stations_crud_and_isolation(stations_h):
    body = {"name": "Shell Ultra City Harrismith", "latitude": -28.2713, "longitude": 29.1352, "radiusKm": 1.5}
    status, s = call(stations_h, "POST", "/stations", body=body)
    assert status == 201 and s["radiusKm"] == 1.5
    assert call(stations_h, "POST", "/stations", body={**body, "latitude": 123})[0] == 400
    assert call(stations_h, "GET", "/stations", tenant="tenant-b")[1]["items"] == []
    assert call(stations_h, "PUT", f"/stations/{s['stationId']}", tenant="tenant-b", body={"name": "hijack"})[0] == 404
    assert call(stations_h, "PUT", f"/stations/{s['stationId']}", body={"radiusKm": 3})[1]["radiusKm"] == 3
    assert call(stations_h, "DELETE", f"/stations/{s['stationId']}")[0] == 200
