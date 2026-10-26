"""
Reference data for major South African freight corridors.

IMPORTANT (data ownership): distances, drive times and toll amounts below are static REFERENCE values,
not live Sanral data. They must be reviewed against the current Sanral tariff schedule by the product owner
before launch and whenever tariffs change (see docs/RUNBOOKS.md, "Reference data review").
Unsupported origin/destination pairs are rejected explicitly - the service never invents an estimate.
"""
from typing import Any, Dict, FrozenSet

from shared.errors import ApiError

DATA_SOURCE = "SmartFleet static reference data (not live Sanral data)"

SA_HUBS: Dict[str, Dict[str, Any]] = {
    "JOHANNESBURG_CITY_DEEP": {"name": "Johannesburg (City Deep Logistics Hub)", "lat": -26.2238, "lon": 28.0934, "province": "Gauteng"},
    "DURBAN_HARBOUR": {"name": "Durban Harbour Container Terminal", "lat": -29.8719, "lon": 31.0264, "province": "KwaZulu-Natal"},
    "CAPE_TOWN_AIRPORT": {"name": "Cape Town Airport Cargo Hub", "lat": -33.9715, "lon": 18.6021, "province": "Western Cape"},
    "PRETORIA_ROSSLYN": {"name": "Pretoria Industrial (Rosslyn Automotive)", "lat": -25.6267, "lon": 28.0903, "province": "Gauteng"},
    "BLOEMFONTEIN_DEPOT": {"name": "Bloemfontein Central Freight Depot", "lat": -29.1181, "lon": 26.2249, "province": "Free State"},
    "NELSPRUIT": {"name": "Nelspruit (Mbombela) Freight Depot", "lat": -25.4753, "lon": 30.9694, "province": "Mpumalanga"},
}

_CORRIDORS: Dict[str, Dict[str, Any]] = {
    "N3_JHB_DBN": {
        "ends": frozenset({"JOHANNESBURG_CITY_DEEP", "DURBAN_HARBOUR"}),
        "corridor": "N3 Freight Corridor (Johannesburg - Durban)",
        "distanceKm": 568.0,
        "estimatedDriveHours": 6.5,
        "tollPlazas": ["De Hoek", "Wilge", "Tugela", "Mooi River", "Marianhill"],
        "tollCostZarClass2": 780.0,
        "suggestedFuelStop": "Harrismith (N3)",
    },
    "N1_JHB_CPT": {
        "ends": frozenset({"JOHANNESBURG_CITY_DEEP", "CAPE_TOWN_AIRPORT"}),
        "corridor": "N1 Freight Corridor (Johannesburg - Cape Town)",
        "distanceKm": 1398.0,
        "estimatedDriveHours": 15.0,
        "tollPlazas": ["Grasmere", "Vaal", "Verkeerdevlei", "Huguenot Tunnel"],
        "tollCostZarClass2": 490.0,
        "suggestedFuelStop": "Bloemfontein / Winelands (N1)",
    },
    "N4_PTA_NLP": {
        "ends": frozenset({"PRETORIA_ROSSLYN", "NELSPRUIT"}),
        "corridor": "N4 Maputo Corridor (Pretoria - Nelspruit)",
        "distanceKm": 345.0,
        "estimatedDriveHours": 4.0,
        "tollPlazas": ["Diamond Hill", "Middelburg", "Machado", "Nkomazi"],
        "tollCostZarClass2": 520.0,
        "suggestedFuelStop": "Middelburg (N4)",
    },
}


def list_reference_data() -> Dict[str, Any]:
    corridors = []
    for key, value in _CORRIDORS.items():
        item = {k: v for k, v in value.items() if k != "ends"}
        item["corridorId"] = key
        item["hubs"] = sorted(value["ends"])
        corridors.append(item)
    return {"corridors": corridors, "hubs": SA_HUBS, "dataSource": DATA_SOURCE}


def plan_route(origin_hub: str, destination_hub: str) -> Dict[str, Any]:
    for hub in (origin_hub, destination_hub):
        if hub not in SA_HUBS:
            raise ApiError(400, "UNKNOWN_HUB", f"Unknown hub '{hub}'.", details={"validHubs": sorted(SA_HUBS)})
    pair: FrozenSet[str] = frozenset({origin_hub, destination_hub})
    for key, corridor in _CORRIDORS.items():
        if corridor["ends"] == pair:
            return {
                "corridorId": key,
                "corridor": corridor["corridor"],
                "origin": SA_HUBS[origin_hub]["name"],
                "destination": SA_HUBS[destination_hub]["name"],
                "distanceKm": corridor["distanceKm"],
                "estimatedDriveHours": corridor["estimatedDriveHours"],
                "tollCostZar": corridor["tollCostZarClass2"],
                "tollPlazas": corridor["tollPlazas"],
                "suggestedFuelStop": corridor["suggestedFuelStop"],
                "dataSource": DATA_SOURCE,
            }
    raise ApiError(422, "NO_CORRIDOR_DATA", "No reference data exists for this origin/destination pair.")
