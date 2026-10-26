import pytest
from conftest import make_event
from shared import fleet_metrics
from shared.auth import UnauthorizedException, get_tenant_id, get_user_id
from shared.errors import ApiError
from shared.geo import check_against_stations, haversine_distance_km
from shared.pagination import decode_cursor, encode_cursor
from shared.response import dumps, error, ok
from shared.utils import calculate_l_per_100km, calculate_rand_per_km, format_zar, in_month
from shared.validation import normalize_timestamp


def test_tenant_comes_only_from_verified_id_token_claims():
    assert get_tenant_id(make_event("GET", "/x", tenant="tenant-a")) == "tenant-a"
    assert get_user_id(make_event("GET", "/x", sub="u-9")) == "u-9"
    for bad in (None, "", "ab", "has space", "x" * 65, "bad/slash"):
        with pytest.raises(UnauthorizedException):
            get_tenant_id(make_event("GET", "/x", tenant=bad))
    with pytest.raises(UnauthorizedException):
        get_tenant_id(make_event("GET", "/x", token_use="access"))


def test_no_development_bypasses_exist():
    """Headers and default tenants were removed: a request without claims is always rejected."""
    event = make_event("GET", "/x", tenant=None)
    event["headers"]["x-dev-tenant-id"] = "tenant-a"
    event["requestContext"]["authorizer"] = {}
    with pytest.raises(UnauthorizedException):
        get_tenant_id(event)
    assert get_tenant_id.__module__ == "shared.auth"
    import shared.auth as auth
    assert not hasattr(auth, "extract_header")


def test_cursor_roundtrip_and_tenant_binding():
    token = encode_cursor({"tenantId": "tenant-a", "tripId": "t1"})
    assert decode_cursor(token, "tenant-a") == {"tenantId": "tenant-a", "tripId": "t1"}
    with pytest.raises(ApiError):
        decode_cursor(token, "tenant-b")
    assert decode_cursor(None, "tenant-a") is None


def test_response_helpers_serialise_decimals_and_set_security_headers():
    from decimal import Decimal
    assert dumps({"a": Decimal("1.50"), "b": Decimal("2")}) == '{"a":1.5,"b":2}'
    r = ok({"x": 1})
    assert r.headers["Cache-Control"] == "no-store" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert "Access-Control-Allow-Origin" not in r.headers      # same-origin; no wildcard CORS
    assert error(404, "NOT_FOUND", "nope").status_code == 404


def test_math_helpers():
    assert calculate_l_per_100km(50, 500) == 10.0 and calculate_l_per_100km(0, 100) == 0.0 and calculate_l_per_100km(10, 0) == 0.0
    assert calculate_rand_per_km(500, 250) == 2.0 and calculate_rand_per_km(-1, 5) == 0.0
    assert format_zar(1250.5) == "R 1,250.50"
    assert in_month("2026-05-03T10:00:00+00:00", __import__("datetime").datetime(2026, 5, 31, tzinfo=__import__("datetime").timezone.utc))
    assert not in_month(None)


def test_timestamps_normalise_to_utc_so_range_keys_sort():
    assert normalize_timestamp("2026-01-05") == "2026-01-05T00:00:00+00:00"
    assert normalize_timestamp("2026-01-05T02:00:00+02:00") == "2026-01-05T00:00:00+00:00"
    with pytest.raises(ValueError):
        normalize_timestamp("not a date")


def test_geo_distance_and_station_states():
    assert 490 < haversine_distance_km(-26.2238, 28.0934, -29.8719, 31.0264) < 505   # great-circle, shorter than the 568 km road
    station = {"stationId": "s1", "name": "Shell", "latitude": -28.2713, "longitude": 29.1352, "radiusKm": 2.0}
    assert check_against_stations(-28.2713, 29.1352, [])["status"] == "NO_STATIONS_CONFIGURED"
    assert check_against_stations(None, None, [station])["status"] == "NO_GPS_DATA"
    assert check_against_stations(-28.2713, 29.1352, [station])["status"] == "AUTHORIZED"
    assert check_against_stations(-28.5, 29.1352, [station])["status"] == "OUTSIDE_AUTHORIZED"


def test_full_tank_efficiency_rejects_degenerate_input():
    assert fleet_metrics.full_tank_efficiency([]) is None
    one = [{"odometerKm": 100, "litres": 10, "fullTank": True, "fillDate": "a"}]
    assert fleet_metrics.full_tank_efficiency(one) is None
    same_odo = one + [{"odometerKm": 100, "litres": 10, "fullTank": True, "fillDate": "b"}]
    assert fleet_metrics.full_tank_efficiency(same_odo) is None
    partials_only = [{"odometerKm": 100, "litres": 10, "fullTank": False}, {"odometerKm": 200, "litres": 10, "fullTank": False}]
    assert fleet_metrics.full_tank_efficiency(partials_only) is None


def test_unknown_route_and_unhandled_errors_do_not_leak_internals(vehicles_h, monkeypatch):
    from conftest import call
    status, body = call(vehicles_h, "GET", "/does-not-exist")
    assert status == 404
    import vehicles.app as app

    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail")
    monkeypatch.setattr(app.repo, "get", boom)
    status, body = call(vehicles_h, "GET", "/vehicles/abc")
    assert status == 500 and "secret-internal-detail" not in str(body) and body["error"]["code"] == "INTERNAL_ERROR"
