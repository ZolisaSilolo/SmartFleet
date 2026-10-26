"""
Pure, deterministic fleet calculations shared by the analytics API, the maintenance API and the AI agent tools.
No I/O here: callers pass already-loaded data. Every formula is defined and documented - there are no
placeholder targets or invented scores. When data is insufficient the result says so explicitly.
"""
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from shared.utils import calculate_rand_per_km, in_month, utc_now

# Statuses that represent maintenance still to be performed (PROPOSED needs human approval first).
ACTIONABLE_MAINTENANCE = {"SCHEDULED", "IN_PROGRESS"}


def efficiency_anomaly_pct() -> float:
    return float(os.environ.get("FUEL_ANOMALY_THRESHOLD_PCT", "15"))


def maintenance_buffer_km() -> float:
    return float(os.environ.get("MAINTENANCE_DUE_ODOMETER_BUFFER_KM", "500"))


def compute_overdue(open_maintenance: Iterable[Dict[str, Any]], vehicles: Iterable[Dict[str, Any]], today: Optional[str] = None) -> List[Dict[str, Any]]:
    """Maintenance that is past its due date, or within the odometer buffer of its due odometer."""
    today = today or utc_now().strftime("%Y-%m-%d")
    by_id = {v["vehicleId"]: v for v in vehicles}
    buffer_km = maintenance_buffer_km()
    alerts: List[Dict[str, Any]] = []
    for record in open_maintenance:
        if record.get("status") not in ACTIONABLE_MAINTENANCE:
            continue
        vehicle = by_id.get(record.get("vehicleId"), {})
        odometer = float(vehicle.get("currentOdometerKm", 0.0))
        due_odometer = record.get("nextDueOdometerKm")
        due_date = record.get("nextDueDate")
        reasons = []
        if due_date and due_date <= today:
            reasons.append(f"Date overdue: due {due_date}")
        if due_odometer is not None:
            remaining = float(due_odometer) - odometer
            if remaining <= 0:
                reasons.append(f"Odometer exceeded by {abs(remaining):.0f} km (at {odometer:.0f} km, due {float(due_odometer):.0f} km)")
            elif remaining <= buffer_km:
                reasons.append(f"Due in {remaining:.0f} km (at {odometer:.0f} km, due {float(due_odometer):.0f} km)")
        if reasons:
            alerts.append({
                "recordId": record.get("recordId"),
                "vehicleId": record.get("vehicleId"),
                "plateNumber": vehicle.get("plateNumber", "Unknown"),
                "serviceType": record.get("serviceType"),
                "status": record.get("status"),
                "reason": " | ".join(reasons),
                "currentOdometerKm": odometer,
                "nextDueOdometerKm": due_odometer,
                "nextDueDate": due_date,
            })
    return alerts


def compute_dashboard(data) -> Dict[str, Any]:
    now = data.now
    revenue = sum(
        float(t.get("revenueZar", 0.0)) for t in data.trips
        if t.get("status") == "COMPLETED" and in_month(t.get("endTime") or t.get("startTime"), now)
    )
    fuel_spend = sum(float(f.get("totalCostZar", 0.0)) for f in data.fuel if in_month(f.get("fillDate"), now))
    maintenance_spend = sum(
        float(m.get("costZar", 0.0)) for m in data.maintenance
        if m.get("status") != "PROPOSED" and in_month(m.get("serviceDate"), now)
    )
    overdue = compute_overdue(data.open_maintenance, data.vehicles, now.strftime("%Y-%m-%d"))
    return {
        "activeVehiclesCount": sum(1 for v in data.vehicles if v.get("status") == "ACTIVE"),
        "totalVehiclesCount": len(data.vehicles),
        "activeTripsCount": sum(1 for t in data.trips if t.get("status") == "IN_PROGRESS"),
        "availableDriversCount": sum(1 for d in data.drivers if d.get("status") == "AVAILABLE"),
        "mtdRevenueZar": round(revenue, 2),
        "mtdFuelSpendZar": round(fuel_spend, 2),
        "mtdMaintenanceSpendZar": round(maintenance_spend, 2),
        "netOperationalCashFlowZar": round(revenue - fuel_spend - maintenance_spend, 2),
        "overdueMaintenanceCount": len(overdue),
        "overdueAlerts": overdue,
    }


def compute_costs(data) -> List[Dict[str, Any]]:
    result = []
    for v in data.vehicles:
        vid = v["vehicleId"]
        distance = sum(float(t.get("distanceKm") or 0.0) for t in data.trips if t.get("vehicleId") == vid and t.get("status") == "COMPLETED")
        fuel_cost = sum(float(f.get("totalCostZar", 0.0)) for f in data.fuel if f.get("vehicleId") == vid)
        maint_cost = sum(float(m.get("costZar", 0.0)) for m in data.maintenance if m.get("vehicleId") == vid and m.get("status") != "PROPOSED")
        result.append({
            "vehicleId": vid, "plateNumber": v.get("plateNumber", ""), "make": v.get("make", ""), "model": v.get("model", ""),
            "totalDistanceKm": round(distance, 1),
            "totalFuelCostZar": round(fuel_cost, 2),
            "totalMaintenanceCostZar": round(maint_cost, 2),
            "totalCostZar": round(fuel_cost + maint_cost, 2),
            "fuelCostPerKm": calculate_rand_per_km(fuel_cost, distance),
            "maintenanceCostPerKm": calculate_rand_per_km(maint_cost, distance),
            "totalCostPerKm": calculate_rand_per_km(fuel_cost + maint_cost, distance),
        })
    return result


def full_tank_efficiency(fuel_logs: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """
    Standard full-tank method. Between the first and last FULL fill-ups (ordered by odometer), the litres put
    in after the first full fill (including partial fills) divided by the distance travelled is consumption.
    Returns None when fewer than two full fills with positive distance exist.
    """
    ordered = sorted(fuel_logs, key=lambda f: (float(f.get("odometerKm", 0.0)), f.get("fillDate", "")))
    full = [f for f in ordered if f.get("fullTank", True)]
    if len(full) < 2:
        return None
    first, last = full[0], full[-1]
    distance = float(last["odometerKm"]) - float(first["odometerKm"])
    if distance <= 0:
        return None
    litres = sum(
        float(f["litres"]) for f in ordered
        if float(first["odometerKm"]) < float(f["odometerKm"]) <= float(last["odometerKm"])
    )
    if litres <= 0:
        return None
    return {"distanceKm": distance, "litres": litres, "lPer100Km": round(litres / distance * 100.0, 2)}


def compute_efficiency(data) -> List[Dict[str, Any]]:
    threshold = efficiency_anomaly_pct()
    result = []
    for v in data.vehicles:
        vid = v["vehicleId"]
        target = float(v.get("targetEfficiencyLPer100Km", 0.0))
        measured = full_tank_efficiency([f for f in data.fuel if f.get("vehicleId") == vid])
        base = {"vehicleId": vid, "plateNumber": v.get("plateNumber", ""), "make": v.get("make", ""), "model": v.get("model", ""),
                "targetEfficiencyLPer100Km": target}
        if measured is None:
            result.append({**base, "totalDistanceKm": 0.0, "totalLitres": 0.0, "actualEfficiencyLPer100Km": None,
                           "variancePercent": None, "status": "INSUFFICIENT_DATA",
                           "anomalyMessage": "At least two full-tank fill-ups with odometer readings are needed."})
            continue
        variance = round((measured["lPer100Km"] - target) / target * 100.0, 1) if target > 0 else 0.0
        anomaly = variance > threshold
        result.append({
            **base,
            "totalDistanceKm": round(measured["distanceKm"], 1),
            "totalLitres": round(measured["litres"], 1),
            "actualEfficiencyLPer100Km": measured["lPer100Km"],
            "variancePercent": variance,
            "status": "ANOMALY_DETECTED" if anomaly else "NORMAL",
            "anomalyMessage": (f"Consumption is {variance}% above target (threshold {threshold:g}%). Check for fuel loss or a mechanical fault."
                               if anomaly else "Within the expected range."),
        })
    return result


UTILISATION_WINDOW_DAYS = 30


def _days_active(trip: Dict[str, Any], window_start: date, window_end: date) -> set:
    try:
        start = datetime.fromisoformat(trip["startTime"]).astimezone(UTC).date()
        end_raw = trip.get("endTime")
        end = datetime.fromisoformat(end_raw).astimezone(UTC).date() if end_raw else window_end
    except (KeyError, ValueError):
        return set()
    start, end = max(start, window_start), min(max(end, start), window_end)
    return {start + timedelta(days=i) for i in range((end - start).days + 1)} if start <= end else set()


def compute_utilisation(data) -> List[Dict[str, Any]]:
    """Utilisation = share of the last 30 days on which the vehicle had a trip in progress or completed."""
    window_end = data.now.astimezone(UTC).date()
    window_start = window_end - timedelta(days=UTILISATION_WINDOW_DAYS - 1)
    result = []
    for v in data.vehicles:
        vid = v["vehicleId"]
        trips = [t for t in data.trips if t.get("vehicleId") == vid and t.get("status") in ("COMPLETED", "IN_PROGRESS")]
        days: set = set()
        for t in trips:
            days |= _days_active(t, window_start, window_end)
        completed = [t for t in trips if t.get("status") == "COMPLETED"]
        result.append({
            "vehicleId": vid, "plateNumber": v.get("plateNumber", ""), "make": v.get("make", ""), "model": v.get("model", ""),
            "vehicleStatus": v.get("status", "ACTIVE"),
            "completedTripsCount": len(completed),
            "activeTripsCount": sum(1 for t in trips if t.get("status") == "IN_PROGRESS"),
            "totalDistanceKm": round(sum(float(t.get("distanceKm") or 0.0) for t in completed), 1),
            "utilisationRatePercent": round(len(days) / UTILISATION_WINDOW_DAYS * 100.0, 1),
        })
    return result
