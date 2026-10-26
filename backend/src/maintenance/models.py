from typing import Literal, Optional

from pydantic import Field
from shared.validation import IsoDate, RequestModel, ResourceId

ServiceType = Literal["ROUTINE_SERVICE", "TYRES", "BRAKES", "ENGINE_REPAIR", "COF_INSPECTION"]
# PROPOSED is created only by the AI agent and must be approved (-> SCHEDULED) by a human.
MaintenanceStatus = Literal["PROPOSED", "SCHEDULED", "IN_PROGRESS", "COMPLETED"]
UserStatus = Literal["SCHEDULED", "IN_PROGRESS", "COMPLETED"]

# Allowed status transitions (anything else is a 409).
TRANSITIONS = {
    "PROPOSED": {"SCHEDULED"},
    "SCHEDULED": {"IN_PROGRESS", "COMPLETED"},
    "IN_PROGRESS": {"COMPLETED", "SCHEDULED"},
    "COMPLETED": set(),
}


class CreateMaintenanceRequest(RequestModel):
    vehicleId: ResourceId
    serviceType: ServiceType
    description: str = Field(..., min_length=3, max_length=500)
    costZar: float = Field(..., ge=0.0, le=10_000_000)
    serviceDate: IsoDate
    odometerAtServiceKm: float = Field(..., ge=0.0, le=5_000_000)
    nextDueOdometerKm: Optional[float] = Field(default=None, ge=0.0, le=5_000_000)
    nextDueDate: Optional[IsoDate] = None
    status: UserStatus = "SCHEDULED"


class UpdateMaintenanceRequest(RequestModel):
    serviceType: Optional[ServiceType] = None
    description: Optional[str] = Field(default=None, min_length=3, max_length=500)
    costZar: Optional[float] = Field(default=None, ge=0.0, le=10_000_000)
    serviceDate: Optional[IsoDate] = None
    odometerAtServiceKm: Optional[float] = Field(default=None, ge=0.0, le=5_000_000)
    nextDueOdometerKm: Optional[float] = Field(default=None, ge=0.0, le=5_000_000)
    nextDueDate: Optional[IsoDate] = None
    status: Optional[UserStatus] = None
