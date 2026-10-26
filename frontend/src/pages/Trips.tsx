import React, { useEffect, useState } from 'react';
import { Plus, Flag } from 'lucide-react';
import { api } from '../services/api';
import { Trip, Vehicle, Driver } from '../types';
import { formatZAR, formatKm, formatDateTimeSA } from '../utils/format';
import { Modal } from '../components/Modal';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Trips: React.FC = () => {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [isStartModalOpen, setIsStartModalOpen] = useState(false);
  const [isEndModalOpen, setIsEndModalOpen] = useState(false);
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);

  // Start Form
  const [vehicleId, setVehicleId] = useState('');
  const [driverId, setDriverId] = useState('');
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [startOdo, setStartOdo] = useState(0);
  const [revenueZar, setRevenueZar] = useState(12000);

  // End Form
  const [endOdo, setEndOdo] = useState(0);
  const [finalRevenue, setFinalRevenue] = useState(0);

  const { run, error } = useAsync();

  const loadData = async () => {
    await run(async () => {
      const [tList, vList, dList] = await Promise.all([api.getTrips(), api.getVehicles(), api.getDrivers()]);
      setTrips(tList);
      setVehicles(vList);
      setDrivers(dList);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleVehicleChange = (vId: string) => {
    setVehicleId(vId);
    const v = vehicles.find((item) => item.vehicleId === vId);
    if (v) {
      setStartOdo(v.currentOdometerKm);
    }
  };

  const handleStartTrip = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() =>
      api.createTrip({
        vehicleId,
        driverId,
        origin,
        destination,
        startOdometerKm: Number(startOdo),
        revenueZar: Number(revenueZar),
      }),
    );
    if (!ok) return;
    setIsStartModalOpen(false);
    resetStartForm();
    await loadData();
  };

  const openEndTrip = (t: Trip) => {
    setSelectedTrip(t);
    setEndOdo(t.startOdometerKm + 350); // Default reasonable trip distance
    setFinalRevenue(t.revenueZar || 0);
    setIsEndModalOpen(true);
  };

  const handleEndTrip = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTrip) return;
    if (endOdo < selectedTrip.startOdometerKm) {
      alert(`End odometer (${endOdo} km) cannot be less than start odometer (${selectedTrip.startOdometerKm} km)`);
      return;
    }
    const ok = await run(() => api.endTrip(selectedTrip.tripId, Number(endOdo), Number(finalRevenue)));
    if (!ok) return;
    setIsEndModalOpen(false);
    setSelectedTrip(null);
    await loadData();
  };

  const resetStartForm = () => {
    setVehicleId('');
    setDriverId('');
    setOrigin('');
    setDestination('');
    setStartOdo(0);
    setRevenueZar(12000);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <ErrorBanner message={error} />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Fleet Trips & Corridor Log</h1>
          <p className="text-sm text-slate-500 mt-1">Track inter-city freight trips, distance run, billings, and driver handoffs.</p>
        </div>
        <button
          onClick={() => {
            resetStartForm();
            if (vehicles.length > 0) handleVehicleChange(vehicles[0].vehicleId);
            if (drivers.length > 0) setDriverId(drivers[0].driverId);
            setIsStartModalOpen(true);
          }}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Dispatch New Trip</span>
        </button>
      </div>

      {/* Trips Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-6 py-3.5">Corridor Route</th>
                <th className="px-6 py-3.5">Vehicle & Driver</th>
                <th className="px-6 py-3.5">Distance</th>
                <th className="px-6 py-3.5">Timing</th>
                <th className="px-6 py-3.5">Revenue (ZAR)</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {trips.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-400">
                    No trips recorded. Dispatch a new trip above.
                  </td>
                </tr>
              ) : (
                trips.map((t) => {
                  const v = vehicles.find((item) => item.vehicleId === t.vehicleId);
                  const d = drivers.find((item) => item.driverId === t.driverId);

                  return (
                    <tr key={t.tripId} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{t.origin}</div>
                        <div className="text-xs text-slate-500 flex items-center space-x-1 mt-0.5">
                          <span>➔ {t.destination}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-900">
                          {v ? `${v.plateNumber} (${v.model})` : 'Vehicle'}
                        </div>
                        <div className="text-xs text-slate-500">
                          Driver: {d ? d.fullName : 'Assigned Driver'}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {t.status === 'COMPLETED' ? (
                          <div>
                            <span className="font-semibold text-slate-900">{formatKm(t.distanceKm || 0)}</span>
                            <div className="text-xs text-slate-400 font-mono">
                              {t.startOdometerKm} ➔ {t.endOdometerKm} km
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-slate-500 font-mono">
                            Start: {formatKm(t.startOdometerKm)}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600">
                        <div>Start: {formatDateTimeSA(t.startTime)}</div>
                        {t.endTime && <div>End: {formatDateTimeSA(t.endTime)}</div>}
                      </td>
                      <td className="px-6 py-4 font-bold text-slate-900">
                        {formatZAR(t.revenueZar || 0)}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            t.status === 'COMPLETED'
                              ? 'bg-emerald-100 text-emerald-800'
                              : t.status === 'IN_PROGRESS'
                              ? 'bg-blue-100 text-blue-800 animate-pulse'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {t.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {t.status === 'IN_PROGRESS' ? (
                          <button
                            onClick={() => openEndTrip(t)}
                            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
                          >
                            <Flag className="w-3.5 h-3.5" />
                            <span>Complete Trip</span>
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400">Archived</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Start Trip Modal */}
      <Modal isOpen={isStartModalOpen} onClose={() => setIsStartModalOpen(false)} title="Dispatch New Trip">
        <form onSubmit={handleStartTrip} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Vehicle</label>
              <select
                required
                value={vehicleId}
                onChange={(e) => handleVehicleChange(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="">Select Vehicle</option>
                {vehicles.map((v) => (
                  <option key={v.vehicleId} value={v.vehicleId}>
                    {v.plateNumber} — {v.make} {v.model} ({v.currentOdometerKm} km)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Driver</label>
              <select
                required
                value={driverId}
                onChange={(e) => setDriverId(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="">Select Driver</option>
                {drivers.map((d) => (
                  <option key={d.driverId} value={d.driverId}>
                    {d.fullName} ({d.status})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Origin (Depot / City)</label>
              <input
                type="text"
                required
                placeholder="e.g. City Deep Logistics Hub, JHB"
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Destination</label>
              <input
                type="text"
                required
                placeholder="e.g. Durban Harbour Port"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Start Odometer (km)</label>
              <input
                type="number"
                required
                min={0}
                value={startOdo}
                onChange={(e) => setStartOdo(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Freight Revenue (ZAR)</label>
              <input
                type="number"
                min={0}
                placeholder="e.g. 15000"
                value={revenueZar}
                onChange={(e) => setRevenueZar(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="pt-2 flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsStartModalOpen(false)}
              className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              Dispatch Trip
            </button>
          </div>
        </form>
      </Modal>

      {/* End Trip Modal */}
      <Modal isOpen={isEndModalOpen} onClose={() => setIsEndModalOpen(false)} title="Complete Trip & Record Odometer">
        <form onSubmit={handleEndTrip} className="space-y-4">
          <div className="p-3 bg-slate-50 rounded-lg text-xs space-y-1">
            <div className="text-slate-500">Route: <span className="font-semibold text-slate-800">{selectedTrip?.origin} ➔ {selectedTrip?.destination}</span></div>
            <div className="text-slate-500">Starting Odometer: <span className="font-mono font-semibold text-slate-800">{selectedTrip?.startOdometerKm} km</span></div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Ending Odometer (km)</label>
            <input
              type="number"
              required
              min={selectedTrip?.startOdometerKm || 0}
              value={endOdo}
              onChange={(e) => setEndOdo(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
            <p className="text-xs text-slate-400 mt-1">
              Calculated Distance: {Math.max(0, endOdo - (selectedTrip?.startOdometerKm || 0))} km
            </p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Confirmed Trip Revenue (ZAR)</label>
            <input
              type="number"
              min={0}
              value={finalRevenue}
              onChange={(e) => setFinalRevenue(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div className="pt-2 flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsEndModalOpen(false)}
              className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              Complete Trip & Free Driver
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
