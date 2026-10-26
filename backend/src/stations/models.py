from typing import Optional

from pydantic import Field
from shared.validation import RequestModel


class CreateStationRequest(RequestModel):
    name: str = Field(..., min_length=2, max_length=120)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radiusKm: float = Field(default=2.0, gt=0.0, le=10.0)
    highway: Optional[str] = Field(default=None, max_length=20)


class UpdateStationRequest(RequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    radiusKm: Optional[float] = Field(default=None, gt=0.0, le=10.0)
    highway: Optional[str] = Field(default=None, max_length=20)
