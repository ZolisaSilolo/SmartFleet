from typing import Literal, Optional

from pydantic import Field
from shared.validation import IsoTimestamp, RequestModel, ResourceId

TripStatus = Literal["IN_PROGRESS", "COMPLETED", "CANCELLED"]


class CreateTripRequest(RequestModel):
    vehicleId: ResourceId
    driverId: ResourceId
    origin: str = Field(..., min_length=2, max_length=120)
    destination: str = Field(..., min_length=2, max_length=120)
    startOdometerKm: float = Field(..., ge=0.0, le=5_000_000)
    startTime: Optional[IsoTimestamp] = None
    revenueZar: float = Field(default=0.0, ge=0.0, le=100_000_000)


class EndTripRequest(RequestModel):
    endOdometerKm: float = Field(..., ge=0.0, le=5_000_000)
    endTime: Optional[IsoTimestamp] = None
    revenueZar: Optional[float] = Field(default=None, ge=0.0, le=100_000_000)
