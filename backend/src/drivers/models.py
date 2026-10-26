from typing import Literal, Optional

from pydantic import Field
from shared.validation import IsoDate, RequestModel, ResourceId, SaPhone

DriverStatus = Literal["AVAILABLE", "ON_TRIP", "OFF_DUTY"]


class CreateDriverRequest(RequestModel):
    fullName: str = Field(..., min_length=2, max_length=100)
    phone: SaPhone
    licenseNumber: str = Field(..., min_length=3, max_length=30)
    licenseExpiryDate: IsoDate
    prdpExpiryDate: Optional[IsoDate] = None
    assignedVehicleId: Optional[ResourceId] = None


class UpdateDriverRequest(RequestModel):
    """ON_TRIP is controlled by the trip workflow and cannot be set directly."""

    fullName: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[SaPhone] = None
    licenseNumber: Optional[str] = Field(default=None, min_length=3, max_length=30)
    licenseExpiryDate: Optional[IsoDate] = None
    prdpExpiryDate: Optional[IsoDate] = None
    assignedVehicleId: Optional[ResourceId] = None
    status: Optional[Literal["AVAILABLE", "OFF_DUTY"]] = None
