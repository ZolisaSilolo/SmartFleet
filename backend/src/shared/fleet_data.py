"""
Bounded, paginated loading of a tenant's operational data for analytics and the AI agent (WA H3).
Uses time-range GSIs so only the analysis window is read; follows all pages; raises rather than truncating.
"""
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Attr, Key
from shared.db import get_table
from shared.pagination import query_all
from shared.utils import days_ago_iso, utc_now

TRIP_PROJECTION = "tripId, vehicleId, driverId, #s, startTime, endTime, distanceKm, revenueZar"
FUEL_PROJECTION = "logId, vehicleId, fillDate, litres, totalCostZar, odometerKm, fullTank, latitude, longitude, stationName"
MAINT_PROJECTION = "recordId, vehicleId, serviceType, #s, costZar, serviceDate, nextDueDate, nextDueOdometerKm"


def lookback_days() -> int:
    return int(os.environ.get("ANALYTICS_LOOKBACK_DAYS", "365"))


@dataclass
class FleetData:
    vehicles: List[Dict[str, Any]]
    drivers: List[Dict[str, Any]]
    trips: List[Dict[str, Any]]
    fuel: List[Dict[str, Any]]
    maintenance: List[Dict[str, Any]]
    open_maintenance: List[Dict[str, Any]]
    window_days: int
    now: datetime


def load_vehicles(tenant_id: str) -> List[Dict[str, Any]]:
    return query_all(get_table("VEHICLES_TABLE"), tenant_id)


def load_stations(tenant_id: str) -> List[Dict[str, Any]]:
    return query_all(get_table("STATIONS_TABLE"), tenant_id)


def load_open_maintenance(tenant_id: str) -> List[Dict[str, Any]]:
    return query_all(
        get_table("MAINTENANCE_TABLE"),
        tenant_id,
        filter_expression=Attr("status").ne("COMPLETED"),
    )


def load_fleet(tenant_id: str, now: Optional[datetime] = None, include_drivers: bool = True) -> FleetData:
    now = now or utc_now()
    days = lookback_days()
    cutoff = days_ago_iso(days, now)
    status_name = {"#s": "status"}

    trips = query_all(
        get_table("TRIPS_TABLE"), tenant_id, index_name="tenant-startTime-index",
        range_condition=Key("startTime").gte(cutoff), projection=TRIP_PROJECTION, names=status_name,
    )
    fuel = query_all(
        get_table("FUEL_TABLE"), tenant_id, index_name="tenant-fillDate-index",
        range_condition=Key("fillDate").gte(cutoff), projection=FUEL_PROJECTION,
    )
    maintenance = query_all(
        get_table("MAINTENANCE_TABLE"), tenant_id, index_name="tenant-serviceDate-index",
        range_condition=Key("serviceDate").gte(cutoff[:10]), projection=MAINT_PROJECTION, names=status_name,
    )
    return FleetData(
        vehicles=load_vehicles(tenant_id),
        drivers=query_all(get_table("DRIVERS_TABLE"), tenant_id) if include_drivers else [],
        trips=trips,
        fuel=fuel,
        maintenance=maintenance,
        open_maintenance=load_open_maintenance(tenant_id),
        window_days=days,
        now=now,
    )
