from typing import Literal, Optional

from pydantic import Field
from shared.validation import RequestModel

VehicleStatus = Literal["ACTIVE", "IN_MAINTENANCE", "INACTIVE"]
FuelType = Literal["DIESEL", "PETROL"]


class CreateVehicleRequest(RequestModel):
    plateNumber: str = Field(..., min_length=2, max_length=20, description="SA registration plate, e.g. CA 123-456")
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=80)
    year: int = Field(..., ge=1990, le=2100)
    fuelType: FuelType = "DIESEL"
    currentOdometerKm: float = Field(default=0.0, ge=0.0, le=5_000_000)
    targetEfficiencyLPer100Km: float = Field(..., gt=0.0, le=200.0)


class UpdateVehicleRequest(RequestModel):
    """IN_MAINTENANCE is controlled by the maintenance workflow and cannot be set directly."""

    plateNumber: Optional[str] = Field(default=None, min_length=2, max_length=20)
    make: Optional[str] = Field(default=None, min_length=1, max_length=50)
    model: Optional[str] = Field(default=None, min_length=1, max_length=80)
    year: Optional[int] = Field(default=None, ge=1990, le=2100)
    fuelType: Optional[FuelType] = None
    currentOdometerKm: Optional[float] = Field(default=None, ge=0.0, le=5_000_000)
    targetEfficiencyLPer100Km: Optional[float] = Field(default=None, gt=0.0, le=200.0)
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = None
