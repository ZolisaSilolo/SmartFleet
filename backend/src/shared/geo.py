"""Geofence verification against the TENANT'S OWN authorised fuel stations (no global/mock station list)."""
import math
from typing import Any, Dict, List, Optional

EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    return round(EARTH_RADIUS_KM * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 3)


def check_against_stations(latitude: Optional[float], longitude: Optional[float], stations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Classify a fill-up location. Outcomes are explicit states, never guesses:
      NO_STATIONS_CONFIGURED  - the tenant has not defined authorised stations, so nothing can be verified
      NO_GPS_DATA             - the fill-up has no coordinates
      AUTHORIZED              - inside the radius of an authorised station
      OUTSIDE_AUTHORIZED      - outside every authorised station radius
    """
    if not stations:
        return {"status": "NO_STATIONS_CONFIGURED", "isVerified": None, "message": "No authorised stations are configured for this fleet."}
    if latitude is None or longitude is None:
        return {"status": "NO_GPS_DATA", "isVerified": None, "message": "Fill-up has no GPS coordinates."}

    nearest, nearest_km = None, float("inf")
    for station in stations:
        distance = haversine_distance_km(latitude, longitude, float(station["latitude"]), float(station["longitude"]))
        if distance < nearest_km:
            nearest, nearest_km = station, distance

    assert nearest is not None
    within = nearest_km <= float(nearest["radiusKm"])
    return {
        "status": "AUTHORIZED" if within else "OUTSIDE_AUTHORIZED",
        "isVerified": within,
        "stationId": nearest["stationId"],
        "stationName": nearest["name"],
        "distanceKm": nearest_km,
        "radiusKm": float(nearest["radiusKm"]),
        "message": (
            f"Fill-up is {nearest_km:.2f} km from {nearest['name']} (radius {float(nearest['radiusKm']):.2f} km)."
            if within
            else f"Fill-up is {nearest_km:.2f} km from the nearest authorised station ({nearest['name']}), outside its {float(nearest['radiusKm']):.2f} km radius."
        ),
    }
