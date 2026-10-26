export interface Page<T> {
  items: T[];
  nextToken: string | null;
}

export type VehicleStatus = 'ACTIVE' | 'IN_MAINTENANCE' | 'INACTIVE';
export type FuelType = 'DIESEL' | 'PETROL';

export interface Vehicle {
  vehicleId: string;
  tenantId?: string;
  plateNumber: string;
  make: string;
  model: string;
  year: number;
  fuelType: FuelType;
  currentOdometerKm: number;
  targetEfficiencyLPer100Km: number;
  status: VehicleStatus;
  activeTripId?: string;
  createdAt?: string;
  updatedAt?: string;
}

export type DriverStatus = 'AVAILABLE' | 'ON_TRIP' | 'OFF_DUTY';

export interface Driver {
  driverId: string;
  tenantId?: string;
  fullName: string;
  phone: string;
  licenseNumber: string;
  licenseExpiryDate: string;
  prdpExpiryDate?: string;
  assignedVehicleId?: string;
  status: DriverStatus;
  activeTripId?: string;
  createdAt?: string;
  updatedAt?: string;
}

export type TripStatus = 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export interface Trip {
  tripId: string;
  tenantId?: string;
  vehicleId: string;
  driverId: string;
  origin: string;
  destination: string;
  startOdometerKm: number;
  endOdometerKm?: number;
  distanceKm?: number;
  startTime: string;
  endTime?: string;
  revenueZar?: number;
  status: TripStatus;
  createdAt?: string;
  updatedAt?: string;
}

export interface FuelLog {
  logId: string;
  tenantId?: string;
  vehicleId: string;
  driverId?: string;
  fillDate: string;
  litres: number;
  costPerLitreZar: number;
  totalCostZar: number;
  odometerKm: number;
  fullTank: boolean;
  stationName?: string;
  latitude: number;
  longitude: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface Station {
  stationId: string;
  name: string;
  latitude: number;
  longitude: number;
  radiusKm: number;
  highway?: string;
}

export type ServiceType = 'ROUTINE_SERVICE' | 'TYRES' | 'BRAKES' | 'ENGINE_REPAIR' | 'COF_INSPECTION';
export type MaintenanceStatus = 'PROPOSED' | 'SCHEDULED' | 'IN_PROGRESS' | 'COMPLETED';
/** Statuses a person may choose when creating a record (PROPOSED is created only by the AI agent). */
export type UserMaintenanceStatus = Exclude<MaintenanceStatus, 'PROPOSED'>;

export interface MaintenanceRecord {
  recordId: string;
  tenantId?: string;
  vehicleId: string;
  serviceType: ServiceType;
  description: string;
  costZar: number;
  serviceDate: string;
  odometerAtServiceKm: number;
  nextDueOdometerKm?: number;
  nextDueDate?: string;
  status: MaintenanceStatus;
  createdAt?: string;
  updatedAt?: string;
}

export interface OverdueAlert {
  recordId?: string;
  vehicleId: string;
  plateNumber: string;
  serviceType: string;
  status?: string;
  reason: string;
  currentOdometerKm?: number;
  nextDueOdometerKm?: number;
  nextDueDate?: string;
}

export interface DashboardStats {
  activeVehiclesCount: number;
  totalVehiclesCount: number;
  activeTripsCount: number;
  availableDriversCount: number;
  mtdRevenueZar: number;
  mtdFuelSpendZar: number;
  mtdMaintenanceSpendZar: number;
  netOperationalCashFlowZar: number;
  overdueMaintenanceCount: number;
  overdueAlerts: OverdueAlert[];
}

export interface Windowed<T> {
  windowDays: number;
  items: T[];
}

export interface CostBreakdown {
  vehicleId: string;
  plateNumber: string;
  make: string;
  model: string;
  totalDistanceKm: number;
  totalFuelCostZar: number;
  totalMaintenanceCostZar: number;
  totalCostZar: number;
  fuelCostPerKm: number;
  maintenanceCostPerKm: number;
  totalCostPerKm: number;
}

export interface EfficiencyMetric {
  vehicleId: string;
  plateNumber: string;
  make: string;
  model: string;
  totalDistanceKm: number;
  totalLitres: number;
  targetEfficiencyLPer100Km: number;
  actualEfficiencyLPer100Km: number | null;
  variancePercent: number | null;
  status: 'NORMAL' | 'ANOMALY_DETECTED' | 'INSUFFICIENT_DATA';
  anomalyMessage: string;
}

export interface UtilisationMetric {
  vehicleId: string;
  plateNumber: string;
  make: string;
  model: string;
  vehicleStatus: VehicleStatus;
  completedTripsCount: number;
  activeTripsCount: number;
  totalDistanceKm: number;
  utilisationRatePercent: number;
}

export interface AiInsight {
  title: string;
  recommendation: string;
  estimatedSavingZar: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface AiInsightsResponse {
  insights: AiInsight[];
  generatedAt: string;
  model: string;
  disclaimer: string;
}

export interface Hub {
  name: string;
  lat: number;
  lon: number;
  province: string;
}

export interface Corridor {
  corridorId: string;
  corridor: string;
  distanceKm: number;
  estimatedDriveHours: number;
  tollPlazas: string[];
  tollCostZarClass2: number;
  suggestedFuelStop: string;
  hubs: string[];
}

export interface CorridorReference {
  corridors: Corridor[];
  hubs: Record<string, Hub>;
  dataSource: string;
}

export interface RoutePlan {
  corridorId: string;
  corridor: string;
  origin: string;
  destination: string;
  distanceKm: number;
  estimatedDriveHours: number;
  tollCostZar: number;
  tollPlazas: string[];
  suggestedFuelStop: string;
  dataSource: string;
}

export type GeofenceStatus = 'NO_STATIONS_CONFIGURED' | 'NO_GPS_DATA' | 'AUTHORIZED' | 'OUTSIDE_AUTHORIZED';

export interface GeofenceCheck {
  status: GeofenceStatus;
  isVerified: boolean | null;
  message: string;
  stationName?: string;
  distanceKm?: number;
  radiusKm?: number;
}

export interface AgentToolExecution {
  tool: string;
  status: string;
  calls?: number;
}

export interface AgentChatResponse {
  response: string;
  engine: string;
  model?: string;
  toolExecutions?: AgentToolExecution[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  engine?: string;
  isError?: boolean;
  toolExecutions?: AgentToolExecution[];
}
