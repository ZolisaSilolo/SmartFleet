from decimal import Decimal

import pytest
from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError
from boto3.dynamodb.types import TypeSerializer
from conftest import FakeContext, call, make_vehicle

SER = TypeSerializer()


def _image(item):
    return {k: SER.serialize(Decimal(str(v)) if isinstance(v, float) else v) for k, v in item.items()}


def stream_event(table, event_name, new, old=None, seq="100"):
    return {"Records": [{
        "eventID": seq, "eventName": event_name, "eventVersion": "1.1", "eventSource": "aws:dynamodb", "awsRegion": "af-south-1",
        "eventSourceARN": f"arn:aws:dynamodb:af-south-1:123456789012:table/test-{table}/stream/2026-01-01T00:00:00.000",
        "dynamodb": {"Keys": {}, "NewImage": _image(new), "OldImage": _image(old or {}), "SequenceNumber": seq, "SizeBytes": 1,
                     "StreamViewType": "NEW_AND_OLD_IMAGES"},
    }]}


@pytest.fixture
def emitted(monkeypatch):
    import events.processor as processor
    events = []
    monkeypatch.setattr(processor, "emit_event", lambda detail_type, source, detail: events.append((detail_type, detail)))
    return events


def run(event):
    import events.processor as processor
    return processor.lambda_handler(event, FakeContext())


def _trip(vehicle, status, end_odo=None):
    item = {"tenantId": "tenant-a", "tripId": "t1", "vehicleId": vehicle["vehicleId"], "driverId": "d1", "status": status, "distanceKm": 568, "revenueZar": 100}
    if end_odo is not None:
        item["endOdometerKm"] = end_odo
    return item


def _odometer(vehicles_h, v):
    return call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[1]["currentOdometerKm"]


def test_trip_completion_updates_odometer_idempotently_and_emits(vehicles_h, emitted):
    v = make_vehicle(vehicles_h, odometer=1000)
    ev = stream_event("TripsTable", "MODIFY", _trip(v, "COMPLETED", 1568), _trip(v, "IN_PROGRESS"))
    assert run(ev)["batchItemFailures"] == []
    assert _odometer(vehicles_h, v) == 1568 and emitted[0][0] == "TripCompleted"
    run(ev)  # at-least-once redelivery is harmless
    assert _odometer(vehicles_h, v) == 1568
    lower = stream_event("TripsTable", "MODIFY", _trip(v, "COMPLETED", 1200), _trip(v, "IN_PROGRESS"))
    run(lower)
    assert _odometer(vehicles_h, v) == 1568  # odometer is monotonic


def test_other_trip_changes_are_ignored(vehicles_h, emitted):
    v = make_vehicle(vehicles_h, odometer=1000)
    run(stream_event("TripsTable", "MODIFY", _trip(v, "COMPLETED", 1500), _trip(v, "COMPLETED", 1500)))  # already completed
    run(stream_event("TripsTable", "MODIFY", _trip(v, "IN_PROGRESS"), _trip(v, "IN_PROGRESS")))
    assert emitted == [] and _odometer(vehicles_h, v) == 1000


def test_failures_are_reported_not_swallowed(vehicles_h, monkeypatch):
    import events.processor as processor
    v = make_vehicle(vehicles_h)

    def boom(*args, **kwargs):
        raise RuntimeError("EventBridge unavailable")
    monkeypatch.setattr(processor, "emit_event", boom)
    # A fully failed batch raises, so Lambda retries it, bisects it and finally ships it to the on-failure SQS destination.
    with pytest.raises(BatchProcessingError):
        run(stream_event("TripsTable", "MODIFY", _trip(v, "COMPLETED", 1500), _trip(v, "IN_PROGRESS"), seq="777"))


def test_mixed_batch_reports_only_the_failing_record(vehicles_h, monkeypatch):
    import events.processor as processor
    v = make_vehicle(vehicles_h)
    good = stream_event("TripsTable", "MODIFY", _trip(v, "COMPLETED", 1500), _trip(v, "IN_PROGRESS"), seq="1")
    bad = stream_event("SomeOtherTable", "MODIFY", {"tenantId": "tenant-a"}, seq="2")
    monkeypatch.setattr(processor, "emit_event", lambda *a, **k: None)
    result = run({"Records": good["Records"] + bad["Records"]})
    assert result["batchItemFailures"] == [{"itemIdentifier": "2"}]   # the good record is NOT retried
    assert _odometer_via_api(v) == 1500


def _odometer_via_api(v):
    from vehicles.app import lambda_handler
    return call(lambda_handler, "GET", f"/vehicles/{v['vehicleId']}")[1]["currentOdometerKm"]


def test_unknown_stream_source_is_a_failure_not_silently_skipped(emitted):
    with pytest.raises(BatchProcessingError):
        run(stream_event("SomeOtherTable", "MODIFY", {"tenantId": "tenant-a", "x": 1}, seq="9"))


def test_real_event_put_failure_is_raised(monkeypatch):
    import events.processor as processor

    class Client:
        def put_events(self, **kwargs):
            return {"FailedEntryCount": 1, "Entries": [{"ErrorCode": "ThrottlingException"}]}
    monkeypatch.setattr(processor, "get_events_client", lambda: Client())
    with pytest.raises(RuntimeError):
        processor.emit_event("X", "smartfleet.test", {"a": 1})


def _fill(fuel_h, v, date, odo, litres, full=True, lat=-28.2713, lon=29.1352):
    status, body = call(fuel_h, "POST", "/fuel", body={"vehicleId": v["vehicleId"], "fillDate": date, "litres": litres, "totalCostZar": litres * 20,
                                                        "odometerKm": odo, "fullTank": full, "latitude": lat, "longitude": lon})
    assert status == 201, body
    return body


def test_fuel_anomaly_uses_full_tank_method_including_partial_fills(vehicles_h, fuel_h, emitted):
    v = make_vehicle(vehicles_h, target=10.0)
    _fill(fuel_h, v, "2026-01-01T00:00:00Z", 1000, 60)
    _fill(fuel_h, v, "2026-01-02T00:00:00Z", 1200, 20, full=False)
    last = _fill(fuel_h, v, "2026-01-03T00:00:00Z", 1400, 30)
    # litres between the two full fills = 20 partial + 30 = 50 over 400 km = 12.5 L/100km -> 25% over target 10
    run(stream_event("FuelTable", "INSERT", last))
    anomaly = [d for t, d in emitted if t == "FuelAnomalyDetected"]
    assert len(anomaly) == 1 and anomaly[0]["actualLPer100Km"] == 12.5 and anomaly[0]["vehicleId"] == v["vehicleId"]


def test_no_anomaly_when_within_threshold_or_data_is_insufficient(vehicles_h, fuel_h, emitted):
    v = make_vehicle(vehicles_h, target=10.0)
    first = _fill(fuel_h, v, "2026-01-01T00:00:00Z", 1000, 60)
    run(stream_event("FuelTable", "INSERT", first))                 # nothing to compare against
    ok_fill = _fill(fuel_h, v, "2026-01-05T00:00:00Z", 1500, 52)    # 10.4 L/100km, within 15%
    run(stream_event("FuelTable", "INSERT", ok_fill))
    assert [t for t, _ in emitted if t == "FuelAnomalyDetected"] == []


def test_geofence_event_only_when_tenant_has_stations(vehicles_h, fuel_h, stations_h, emitted):
    v = make_vehicle(vehicles_h)
    far = _fill(fuel_h, v, "2026-01-01T00:00:00Z", 1000, 40, lat=-28.75, lon=28.84)
    run(stream_event("FuelTable", "INSERT", far))
    assert [t for t, _ in emitted if t == "FuelOffGeofence"] == []   # nothing configured => cannot judge
    call(stations_h, "POST", "/stations", body={"name": "Shell Harrismith", "latitude": -28.2713, "longitude": 29.1352, "radiusKm": 2})
    run(stream_event("FuelTable", "INSERT", far))
    off = [d for t, d in emitted if t == "FuelOffGeofence"]
    assert len(off) == 1 and off[0]["distanceKm"] > 30
    near = _fill(fuel_h, v, "2026-01-02T00:00:00Z", 1400, 40)
    run(stream_event("FuelTable", "INSERT", near))
    assert len([t for t, _ in emitted if t == "FuelOffGeofence"]) == 1


def test_tenant_stations_do_not_leak_across_tenants(vehicles_h, fuel_h, stations_h, emitted):
    call(stations_h, "POST", "/stations", tenant="tenant-b", body={"name": "B station", "latitude": -28.75, "longitude": 28.84, "radiusKm": 2})
    v = make_vehicle(vehicles_h)
    fill = _fill(fuel_h, v, "2026-01-01T00:00:00Z", 1000, 40, lat=-28.75, lon=28.84)
    run(stream_event("FuelTable", "INSERT", fill))
    assert [t for t, _ in emitted if t == "FuelOffGeofence"] == []  # tenant-a has no stations of its own
