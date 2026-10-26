import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def current_iso_time() -> str:
    return utc_now().isoformat()


def current_iso_date() -> str:
    return utc_now().strftime("%Y-%m-%d")


def month_start_iso(now: Optional[datetime] = None) -> str:
    now = now or utc_now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def days_ago_iso(days: int, now: Optional[datetime] = None) -> str:
    now = now or utc_now()
    return (now - timedelta(days=days)).isoformat()


def calculate_l_per_100km(litres: float, distance_km: float) -> float:
    """Litres per 100 km = litres / distance * 100. Returns 0.0 when inputs are not positive."""
    if distance_km <= 0 or litres <= 0:
        return 0.0
    return round((litres / distance_km) * 100.0, 2)


def calculate_rand_per_km(total_cost_zar: float, distance_km: float) -> float:
    """Rand per km. Returns 0.0 when inputs are not positive."""
    if distance_km <= 0 or total_cost_zar <= 0:
        return 0.0
    return round(total_cost_zar / distance_km, 2)


def format_zar(amount: float) -> str:
    return f"R {amount:,.2f}"


def in_month(date_str: Optional[str], now: Optional[datetime] = None) -> bool:
    """True if an ISO date/timestamp falls in the current UTC year+month."""
    if not date_str:
        return False
    now = now or utc_now()
    return date_str[:7] == now.strftime("%Y-%m")
