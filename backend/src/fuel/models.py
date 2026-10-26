from typing import Optional

from pydantic import Field, model_validator
from shared.validation import IsoTimestamp, RequestModel, ResourceId


class CreateFuelRequest(RequestModel):
    vehicleId: ResourceId
    driverId: Optional[ResourceId] = None
    fillDate: IsoTimestamp
    litres: float = Field(..., gt=0.0, le=2000.0)
    costPerLitreZar: Optional[float] = Field(default=None, gt=0.0, le=500.0)
    totalCostZar: Optional[float] = Field(default=None, gt=0.0, le=1_000_000.0)
    odometerKm: float = Field(..., ge=0.0, le=5_000_000)
    fullTank: bool = Field(default=True, description="True if the tank was filled completely (needed for L/100km)")
    stationName: Optional[str] = Field(default=None, max_length=120)
    latitude: float = Field(..., ge=-90.0, le=90.0, description="GPS latitude of the fill-up")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="GPS longitude of the fill-up")

    @model_validator(mode="after")
    def _require_a_price(self):
        if self.costPerLitreZar is None and self.totalCostZar is None:
            raise ValueError("Provide costPerLitreZar or totalCostZar - prices are never assumed")
        if self.costPerLitreZar is not None and self.totalCostZar is not None:
            expected = self.litres * self.costPerLitreZar
            if abs(expected - self.totalCostZar) > max(1.0, 0.01 * expected):
                raise ValueError("totalCostZar does not match litres x costPerLitreZar")
        return self
