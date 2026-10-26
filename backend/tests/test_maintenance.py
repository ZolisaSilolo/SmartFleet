from datetime import date, timedelta

from conftest import call, make_driver, make_vehicle


def _record(maint_h, vehicle, tenant="tenant-a", **overrides):
    body = {"vehicleId": vehicle["vehicleId"], "serviceType": "ROUTINE_SERVICE", "description": "15000km service", "costZar": 4500,
            "serviceDate": "2026-01-15", "odometerAtServiceKm": 15000}
    body.update(overrides)
    return call(maint_h, "POST", "/maintenance", tenant=tenant, body=body)


def _vehicle_status(vehicles_h, v):
    return call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[1]["status"]


def test_workshop_lifecycle_updates_vehicle_atomically(maint_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    status, rec = _record(maint_h, v)
    assert status == 201 and rec["status"] == "SCHEDULED" and _vehicle_status(vehicles_h, v) == "ACTIVE"
    status, rec = call(maint_h, "PUT", f"/maintenance/{rec['recordId']}", body={"status": "IN_PROGRESS"})
    assert status == 200 and _vehicle_status(vehicles_h, v) == "IN_MAINTENANCE"
    assert call(maint_h, "DELETE", f"/maintenance/{rec['recordId']}")[0] == 409  # work in progress
    status, rec = call(maint_h, "PUT", f"/maintenance/{rec['recordId']}", body={"status": "COMPLETED"})
    assert status == 200 and rec["status"] == "COMPLETED" and _vehicle_status(vehicles_h, v) == "ACTIVE"


def test_invalid_transition_and_only_one_job_in_workshop(maint_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    done = _record(maint_h, v, status="COMPLETED")[1]
    status, body = call(maint_h, "PUT", f"/maintenance/{done['recordId']}", body={"status": "IN_PROGRESS"})
    assert status == 409 and body["error"]["code"] == "INVALID_TRANSITION"
    assert _record(maint_h, v, status="IN_PROGRESS")[0] == 201
    status, _ = _record(maint_h, v, status="IN_PROGRESS")  # vehicle already in the workshop
    assert status == 409


def test_vehicle_on_a_trip_cannot_enter_the_workshop(maint_h, vehicles_h, drivers_h, trips_h):
    v, d = make_vehicle(vehicles_h), make_driver(drivers_h)
    call(trips_h, "POST", "/trips", body={"vehicleId": v["vehicleId"], "driverId": d["driverId"], "origin": "AA", "destination": "BB", "startOdometerKm": 1000})
    assert _record(maint_h, v, status="IN_PROGRESS")[0] == 409
    assert _vehicle_status(vehicles_h, v) == "ACTIVE"


def test_unknown_vehicle_and_tenant_isolation(maint_h, vehicles_h):
    foreign = make_vehicle(vehicles_h, tenant="tenant-b")
    assert _record(maint_h, foreign, tenant="tenant-a")[0] == 404
    v = make_vehicle(vehicles_h)
    rec = _record(maint_h, v)[1]
    assert call(maint_h, "GET", f"/maintenance/{rec['recordId']}", tenant="tenant-b")[0] == 404
    assert call(maint_h, "PUT", f"/maintenance/{rec['recordId']}", tenant="tenant-b", body={"costZar": 1})[0] == 404
    assert call(maint_h, "PUT", f"/maintenance/{rec['recordId']}", body={"status": "PROPOSED"})[0] == 400  # agent-only status


def test_proposed_requires_human_approval_transition(maint_h, vehicles_h):
    from shared.repo import TenantRepo
    v = make_vehicle(vehicles_h)
    item = {"tenantId": "tenant-a", "recordId": "rec-1", "vehicleId": v["vehicleId"], "serviceType": "BRAKES", "description": "[AI proposal] pads",
            "costZar": 3000, "serviceDate": "2026-01-01", "odometerAtServiceKm": 1000, "status": "PROPOSED", "createdAt": "x", "updatedAt": "x"}
    TenantRepo("MAINTENANCE_TABLE", "recordId", "Maintenance record").create(item)
    assert call(maint_h, "PUT", "/maintenance/rec-1", body={"status": "COMPLETED"})[0] == 409
    assert call(maint_h, "PUT", "/maintenance/rec-1", body={"status": "SCHEDULED"})[1]["status"] == "SCHEDULED"


def test_due_list_uses_dates_and_odometer_buffer(maint_h, vehicles_h):
    v = make_vehicle(vehicles_h, odometer=14800)
    overdue_date = (date.today() - timedelta(days=3)).isoformat()
    _record(maint_h, v, description="date overdue", nextDueDate=overdue_date)
    _record(maint_h, v, description="odometer close", nextDueOdometerKm=15000)
    _record(maint_h, v, description="far away", nextDueOdometerKm=90000, nextDueDate="2099-01-01")
    _record(maint_h, v, description="already done", status="COMPLETED", nextDueDate=overdue_date)
    due = call(maint_h, "GET", "/maintenance/due")[1]["items"]
    assert len(due) == 2 and all(i["plateNumber"] == "CA 111-111" for i in due)
    assert call(maint_h, "GET", "/maintenance/due", tenant="tenant-b")[1]["items"] == []


def test_list_and_filters(maint_h, vehicles_h):
    v = make_vehicle(vehicles_h)
    _record(maint_h, v, serviceDate="2026-01-01")
    _record(maint_h, v, serviceDate="2026-02-01", status="COMPLETED")
    items = call(maint_h, "GET", "/maintenance")[1]["items"]
    assert [i["serviceDate"] for i in items] == ["2026-02-01", "2026-01-01"]
    assert len(call(maint_h, "GET", "/maintenance", query={"status": "completed"})[1]["items"]) == 1
