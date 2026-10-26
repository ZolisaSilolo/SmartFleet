from datetime import UTC, datetime, timedelta

from conftest import call, make_driver, make_vehicle

NOW = datetime.now(UTC)


def _iso(days_ago=0):
    return (NOW - timedelta(hours=1, days=days_ago)).isoformat()


def _complete_trip(trips_h, v, d, start_odo, end_odo, revenue):
    trip = call(trips_h, "POST", "/trips", body={"vehicleId": v["vehicleId"], "driverId": d["driverId"], "origin": "AA", "destination": "BB",
                                                  "startOdometerKm": start_odo, "revenueZar": 0})[1]
    status, done = call(trips_h, "POST", f"/trips/{trip['tripId']}/end", body={"endOdometerKm": end_odo, "revenueZar": revenue})
    assert status == 200, done
    return done


def _fill(fuel_h, v, odo, litres, cost, days_ago=0, full=True):
    status, body = call(fuel_h, "POST", "/fuel", body={"vehicleId": v["vehicleId"], "fillDate": _iso(days_ago), "litres": litres, "totalCostZar": cost,
                                                        "odometerKm": odo, "fullTank": full, "latitude": -26.2, "longitude": 28.0})
    assert status == 201, body


def test_dashboard_month_to_date_financials(analytics_h, vehicles_h, drivers_h, trips_h, fuel_h, maint_h):
    v, d = make_vehicle(vehicles_h, odometer=1000), make_driver(drivers_h)
    _complete_trip(trips_h, v, d, 1000, 1500, 15000)
    _fill(fuel_h, v, 1500, 50, 1000)
    call(maint_h, "POST", "/maintenance", body={"vehicleId": v["vehicleId"], "serviceType": "TYRES", "description": "two tyres", "costZar": 500,
                                                "serviceDate": NOW.strftime("%Y-%m-%d"), "odometerAtServiceKm": 1500, "status": "COMPLETED"})
    status, dash = call(analytics_h, "GET", "/analytics/dashboard")
    assert status == 200
    assert dash["mtdRevenueZar"] == 15000 and dash["mtdFuelSpendZar"] == 1000 and dash["mtdMaintenanceSpendZar"] == 500
    assert dash["netOperationalCashFlowZar"] == 13500 and dash["totalVehiclesCount"] == 1 and dash["availableDriversCount"] == 1


def test_old_data_outside_the_window_is_excluded(analytics_h, vehicles_h, fuel_h):
    v = make_vehicle(vehicles_h)
    _fill(fuel_h, v, 100, 40, 800, days_ago=900)
    costs = call(analytics_h, "GET", "/analytics/costs")[1]
    assert costs["windowDays"] == 365 and costs["items"][0]["totalFuelCostZar"] == 0


def test_costs_per_km(analytics_h, vehicles_h, drivers_h, trips_h, fuel_h):
    v, d = make_vehicle(vehicles_h, odometer=0), make_driver(drivers_h)
    _complete_trip(trips_h, v, d, 0, 400, 0)
    _fill(fuel_h, v, 400, 40, 800)
    item = call(analytics_h, "GET", "/analytics/costs")[1]["items"][0]
    assert item["totalDistanceKm"] == 400 and item["fuelCostPerKm"] == 2.0 and item["totalCostPerKm"] == 2.0


def test_efficiency_needs_two_full_fills_and_never_invents_a_value(analytics_h, vehicles_h, fuel_h):
    v = make_vehicle(vehicles_h, target=10.0)
    assert call(analytics_h, "GET", "/analytics/efficiency")[1]["items"][0]["status"] == "INSUFFICIENT_DATA"
    _fill(fuel_h, v, 1000, 60, 1200, days_ago=10)
    item = call(analytics_h, "GET", "/analytics/efficiency")[1]["items"][0]
    assert item["status"] == "INSUFFICIENT_DATA" and item["actualEfficiencyLPer100Km"] is None
    _fill(fuel_h, v, 1400, 56, 1100, days_ago=5)            # 56 L / 400 km = 14 L/100km vs target 10 => +40%
    item = call(analytics_h, "GET", "/analytics/efficiency")[1]["items"][0]
    assert item["status"] == "ANOMALY_DETECTED" and item["actualEfficiencyLPer100Km"] == 14.0 and item["variancePercent"] == 40.0
    _fill(fuel_h, v, 1800, 42, 800, days_ago=2)
    item = call(analytics_h, "GET", "/analytics/efficiency")[1]["items"][0]
    assert item["totalDistanceKm"] == 800 and item["totalLitres"] == 98            # (56 + 42) / 800 = 12.25 L/100km
    assert item["actualEfficiencyLPer100Km"] == 12.25 and item["status"] == "ANOMALY_DETECTED"


def test_utilisation_is_share_of_days_with_a_trip(analytics_h, vehicles_h, drivers_h, trips_h):
    v, d = make_vehicle(vehicles_h, odometer=0), make_driver(drivers_h)
    assert call(analytics_h, "GET", "/analytics/utilisation")[1]["items"][0]["utilisationRatePercent"] == 0.0
    _complete_trip(trips_h, v, d, 0, 100, 0)
    item = call(analytics_h, "GET", "/analytics/utilisation")[1]["items"][0]
    assert item["utilisationRatePercent"] == round(1 / 30 * 100, 1) and item["completedTripsCount"] == 1


def test_analytics_are_tenant_scoped(analytics_h, vehicles_h, fuel_h):
    v = make_vehicle(vehicles_h)
    _fill(fuel_h, v, 1000, 50, 1000)
    assert call(analytics_h, "GET", "/analytics/costs", tenant="tenant-b")[1]["items"] == []
    dash = call(analytics_h, "GET", "/analytics/dashboard", tenant="tenant-b")[1]
    assert dash["totalVehiclesCount"] == 0 and dash["mtdFuelSpendZar"] == 0
    assert call(analytics_h, "GET", "/analytics/dashboard", tenant=None)[0] == 401


def test_corridor_reference_data_and_explicit_failures(analytics_h):
    status, ref = call(analytics_h, "GET", "/analytics/corridors")
    assert status == 200 and "not live Sanral" in ref["dataSource"] and "DURBAN_HARBOUR" in ref["hubs"]
    status, plan = call(analytics_h, "POST", "/analytics/plan-route", body={"originHub": "DURBAN_HARBOUR", "destinationHub": "JOHANNESBURG_CITY_DEEP"})
    assert status == 200 and plan["corridorId"] == "N3_JHB_DBN" and plan["distanceKm"] == 568.0
    status, body = call(analytics_h, "POST", "/analytics/plan-route", body={"originHub": "DURBAN_HARBOUR", "destinationHub": "NELSPRUIT"})
    assert status == 422 and body["error"]["code"] == "NO_CORRIDOR_DATA"        # no invented estimate
    assert call(analytics_h, "POST", "/analytics/plan-route", body={"originHub": "Mars", "destinationHub": "NELSPRUIT"})[0] == 400
    assert call(analytics_h, "POST", "/analytics/plan-route", body={"originHub": "DURBAN_HARBOUR"})[0] == 400


def test_geofence_verification_states(analytics_h, stations_h):
    probe = {"latitude": -28.2713, "longitude": 29.1352}
    assert call(analytics_h, "POST", "/analytics/verify-fuel-location", body=probe)[1]["status"] == "NO_STATIONS_CONFIGURED"
    call(stations_h, "POST", "/stations", body={"name": "Shell Harrismith", "latitude": -28.2713, "longitude": 29.1352, "radiusKm": 1})
    inside = call(analytics_h, "POST", "/analytics/verify-fuel-location", body=probe)[1]
    assert inside["status"] == "AUTHORIZED" and inside["isVerified"] is True
    outside = call(analytics_h, "POST", "/analytics/verify-fuel-location", body={"latitude": -28.75, "longitude": 28.84})[1]
    assert outside["status"] == "OUTSIDE_AUTHORIZED" and outside["isVerified"] is False and outside["distanceKm"] > 30
    assert call(analytics_h, "POST", "/analytics/verify-fuel-location", body={"latitude": 999, "longitude": 0})[0] == 400
    assert call(analytics_h, "POST", "/analytics/verify-fuel-location", tenant="tenant-b", body=probe)[1]["status"] == "NO_STATIONS_CONFIGURED"
