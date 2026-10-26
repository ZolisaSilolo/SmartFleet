import {
  AgentChatResponse,
  AiInsightsResponse,
  CorridorReference,
  CostBreakdown,
  DashboardStats,
  Driver,
  EfficiencyMetric,
  FuelLog,
  GeofenceCheck,
  MaintenanceRecord,
  OverdueAlert,
  RoutePlan,
  Station,
  Trip,
  UtilisationMetric,
  Vehicle,
  Windowed,
} from '../types';
import { listAll, request } from './http';

/** Typed client for the SmartFleet API. Every call is authenticated with the signed-in user's Cognito ID token. */
export const api = {
  // --- Vehicles ---
  getVehicles: () => listAll<Vehicle>('/vehicles'),
  createVehicle: (payload: Pick<Vehicle, 'plateNumber' | 'make' | 'model' | 'year' | 'fuelType' | 'currentOdometerKm' | 'targetEfficiencyLPer100Km'>) =>
    request<Vehicle>('POST', '/vehicles', payload),
  updateVehicle: (id: string, payload: Partial<Pick<Vehicle, 'currentOdometerKm' | 'targetEfficiencyLPer100Km'>> & { status?: 'ACTIVE' | 'INACTIVE' }) =>
    request<Vehicle>('PUT', `/vehicles/${id}`, payload),
  deleteVehicle: (id: string) => request<void>('DELETE', `/vehicles/${id}`),

  // --- Drivers ---
  getDrivers: () => listAll<Driver>('/drivers'),
  createDriver: (payload: Pick<Driver, 'fullName' | 'phone' | 'licenseNumber' | 'licenseExpiryDate'> & Partial<Pick<Driver, 'prdpExpiryDate' | 'assignedVehicleId'>>) =>
    request<Driver>('POST', '/drivers', payload),
  updateDriver: (id: string, payload: Partial<Pick<Driver, 'phone' | 'prdpExpiryDate' | 'assignedVehicleId'>> & { status?: 'AVAILABLE' | 'OFF_DUTY' }) =>
    request<Driver>('PUT', `/drivers/${id}`, payload),
  deleteDriver: (id: string) => request<void>('DELETE', `/drivers/${id}`),

  // --- Stations ---
  getStations: () => listAll<Station>('/stations'),
  createStation: (payload: Omit<Station, 'stationId'>) => request<Station>('POST', '/stations', payload),
  updateStation: (id: string, payload: Partial<Omit<Station, 'stationId'>>) => request<Station>('PUT', `/stations/${id}`, payload),
  deleteStation: (id: string) => request<void>('DELETE', `/stations/${id}`),

  // --- Trips ---
  getTrips: () => listAll<Trip>('/trips'),
  createTrip: (payload: Pick<Trip, 'vehicleId' | 'driverId' | 'origin' | 'destination' | 'startOdometerKm'> & { revenueZar?: number }) =>
    request<Trip>('POST', '/trips', payload),
  endTrip: (id: string, endOdometerKm: number, revenueZar?: number) =>
    request<Trip>('POST', `/trips/${id}/end`, { endOdometerKm, ...(revenueZar !== undefined ? { revenueZar } : {}) }),
  cancelTrip: (id: string) => request<Trip>('POST', `/trips/${id}/cancel`),

  // --- Fuel ---
  getFuel: () => listAll<FuelLog>('/fuel'),
  createFuel: (payload: {
    vehicleId: string;
    driverId?: string;
    fillDate: string;
    litres: number;
    costPerLitreZar: number;
    odometerKm: number;
    fullTank: boolean;
    stationName?: string;
    latitude: number;
    longitude: number;
  }) => request<FuelLog>('POST', '/fuel', payload),
  deleteFuel: (id: string) => request<void>('DELETE', `/fuel/${id}`),

  // --- Maintenance ---
  getMaintenance: () => listAll<MaintenanceRecord>('/maintenance'),
  getMaintenanceDue: async () => (await request<{ items: OverdueAlert[] }>('GET', '/maintenance/due')).items,
  createMaintenance: (payload: Omit<MaintenanceRecord, 'recordId' | 'status'> & { status: Exclude<MaintenanceRecord['status'], 'PROPOSED'> }) =>
    request<MaintenanceRecord>('POST', '/maintenance', payload),
  updateMaintenance: (id: string, payload: { status: Exclude<MaintenanceRecord['status'], 'PROPOSED'> }) =>
    request<MaintenanceRecord>('PUT', `/maintenance/${id}`, payload),
  deleteMaintenance: (id: string) => request<void>('DELETE', `/maintenance/${id}`),

  // --- Analytics ---
  getDashboard: () => request<DashboardStats>('GET', '/analytics/dashboard'),
  getCosts: () => request<Windowed<CostBreakdown>>('GET', '/analytics/costs'),
  getEfficiency: () => request<Windowed<EfficiencyMetric>>('GET', '/analytics/efficiency'),
  getUtilisation: () => request<Windowed<UtilisationMetric>>('GET', '/analytics/utilisation'),
  getCorridors: () => request<CorridorReference>('GET', '/analytics/corridors'),
  planRoute: (originHub: string, destinationHub: string) => request<RoutePlan>('POST', '/analytics/plan-route', { originHub, destinationHub }),
  verifyFuelLocation: (latitude: number, longitude: number) => request<GeofenceCheck>('POST', '/analytics/verify-fuel-location', { latitude, longitude }),

  // --- AI (no offline fallback: failures surface to the user) ---
  getAiInsights: () => request<AiInsightsResponse>('POST', '/analytics/ai-insights'),
  sendAgentMessage: (message: string) => request<AgentChatResponse>('POST', '/agent/chat', { message }),
};

export const analyticsApi = api;
