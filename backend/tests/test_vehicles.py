from conftest import call, make_vehicle


def test_requires_verified_id_token_claims(vehicles_h):
    assert call(vehicles_h, "GET", "/vehicles", tenant=None)[0] == 401          # no tenant claim
    assert call(vehicles_h, "GET", "/vehicles", token_use="access")[0] == 401   # access tokens carry no tenant


def test_crud_roundtrip(vehicles_h):
    v = make_vehicle(vehicles_h)
    assert v["tenantId"] == "tenant-a" and v["status"] == "ACTIVE" and v["plateNumber"] == "CA 111-111"
    assert call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[1]["make"] == "Isuzu"
    status, updated = call(vehicles_h, "PUT", f"/vehicles/{v['vehicleId']}", body={"model": "FVR", "status": "INACTIVE"})
    assert status == 200 and updated["model"] == "FVR" and updated["status"] == "INACTIVE"
    assert call(vehicles_h, "DELETE", f"/vehicles/{v['vehicleId']}")[0] == 200
    assert call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[0] == 404
    assert call(vehicles_h, "DELETE", f"/vehicles/{v['vehicleId']}")[0] == 404  # deletes are not silent


def test_unknown_and_privileged_fields_are_rejected(vehicles_h):
    status, body = call(vehicles_h, "POST", "/vehicles", body={
        "plateNumber": "CA 1", "make": "A", "model": "B", "year": 2022, "targetEfficiencyLPer100Km": 10, "tenantId": "tenant-b"})
    assert status == 400 and body["error"]["code"] == "VALIDATION_ERROR"
    v = make_vehicle(vehicles_h)
    assert call(vehicles_h, "PUT", f"/vehicles/{v['vehicleId']}", body={"status": "IN_MAINTENANCE"})[0] == 400


def test_validation_and_bad_ids(vehicles_h):
    assert call(vehicles_h, "POST", "/vehicles", body={"plateNumber": "X"})[0] == 400
    assert call(vehicles_h, "GET", "/vehicles/..%2F..")[0] in (400, 404)
    assert call(vehicles_h, "POST", "/vehicles", body=[1, 2])[0] == 400


def test_plate_must_be_unique_per_tenant_but_not_across_tenants(vehicles_h):
    make_vehicle(vehicles_h, plate="CA 222-222")
    status, body = call(vehicles_h, "POST", "/vehicles", body={
        "plateNumber": "ca 222-222", "make": "A", "model": "B", "year": 2022, "targetEfficiencyLPer100Km": 10})
    assert status == 409 and body["error"]["code"] == "PLATE_EXISTS"
    make_vehicle(vehicles_h, tenant="tenant-b", plate="CA 222-222")  # another tenant may reuse the plate


def test_tenant_isolation(vehicles_h):
    v = make_vehicle(vehicles_h, tenant="tenant-a")
    vid = v["vehicleId"]
    assert call(vehicles_h, "GET", f"/vehicles/{vid}", tenant="tenant-b")[0] == 404
    assert call(vehicles_h, "PUT", f"/vehicles/{vid}", tenant="tenant-b", body={"model": "hijack"})[0] == 404
    assert call(vehicles_h, "DELETE", f"/vehicles/{vid}", tenant="tenant-b")[0] == 404
    assert call(vehicles_h, "GET", "/vehicles", tenant="tenant-b")[1]["items"] == []
    assert call(vehicles_h, "GET", f"/vehicles/{vid}", tenant="tenant-a")[1]["model"] == "NPR 400"  # untouched


def test_pagination_follows_cursor_and_rejects_foreign_cursor(vehicles_h):
    for i in range(5):
        make_vehicle(vehicles_h, plate=f"CA {i}00-000")
    seen, token = [], None
    while True:
        query = {"limit": "2", **({"nextToken": token} if token else {})}
        status, body = call(vehicles_h, "GET", "/vehicles", query=query)
        assert status == 200 and len(body["items"]) <= 2
        seen += [i["vehicleId"] for i in body["items"]]
        token = body["nextToken"]
        if not token:
            break
    assert len(seen) == 5 and len(set(seen)) == 5

    _, first = call(vehicles_h, "GET", "/vehicles", query={"limit": "1"})
    status, body = call(vehicles_h, "GET", "/vehicles", tenant="tenant-b", query={"nextToken": first["nextToken"]})
    assert status == 400 and body["error"]["code"] == "INVALID_CURSOR"
    assert call(vehicles_h, "GET", "/vehicles", query={"limit": "9999"})[0] == 400
    assert call(vehicles_h, "GET", "/vehicles", query={"nextToken": "garbage"})[0] == 400


def test_status_filter(vehicles_h):
    make_vehicle(vehicles_h, plate="CA 1")
    b = make_vehicle(vehicles_h, plate="CA 2")
    call(vehicles_h, "PUT", f"/vehicles/{b['vehicleId']}", body={"status": "INACTIVE"})
    items = call(vehicles_h, "GET", "/vehicles", query={"status": "inactive"})[1]["items"]
    assert [i["vehicleId"] for i in items] == [b["vehicleId"]]
