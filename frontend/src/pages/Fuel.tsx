import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Droplet, DollarSign, Gauge } from 'lucide-react';
import { api } from '../services/api';
import { FuelLog, Vehicle, Driver } from '../types';
import { formatZAR, formatKm, formatDateTimeSA } from '../utils/format';
import { Modal } from '../components/Modal';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Fuel: React.FC = () => {
  const [fuelLogs, setFuelLogs] = useState<FuelLog[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form State
  const [vehicleId, setVehicleId] = useState('');
  const [driverId, setDriverId] = useState('');
  const [fillDate, setFillDate] = useState(new Date().toISOString().slice(0, 16));
  const [litres, setLitres] = useState(70.0);
  const [costPerLitre, setCostPerLitre] = useState(24.30);
  const [odometer, setOdometer] = useState(50000);
  const [stationName, setStationName] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [fullTank, setFullTank] = useState(true);
  const [locating, setLocating] = useState(false);
  const { run, error, setError } = useAsync();

  const loadData = async () => {
    await run(async () => {
      const [fList, vList, dList] = await Promise.all([api.getFuel(), api.getVehicles(), api.getDrivers()]);
      setFuelLogs(fList);
      setVehicles(vList);
      setDrivers(dList);
    });
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setError('This device cannot provide a location. Enter the coordinates manually.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude.toFixed(6));
        setLongitude(pos.coords.longitude.toFixed(6));
        setLocating(false);
      },
      () => {
        setError('Location permission was denied. Enter the coordinates manually.');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleVehicleChange = (vId: string) => {
    setVehicleId(vId);
    const v = vehicles.find((item) => item.vehicleId === vId);
    if (v) {
      setOdometer(v.currentOdometerKm);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() =>
      api.createFuel({
        vehicleId,
        driverId: driverId || undefined,
        fillDate: new Date(fillDate).toISOString(),
        litres: Number(litres),
        costPerLitreZar: Number(costPerLitre),
        odometerKm: Number(odometer),
        fullTank,
        stationName: stationName || undefined,
        latitude: Number(latitude),
        longitude: Number(longitude),
      }),
    );
    if (!ok) return;
    setIsModalOpen(false);
    resetForm();
    await loadData();
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this fuel transaction record?')) {
      if (await run(() => api.deleteFuel(id))) await loadData();
    }
  };

  const resetForm = () => {
    setVehicleId('');
    setDriverId('');
    setLitres(70.0);
    setCostPerLitre(24.30);
    setStationName('');
    setLatitude('');
    setLongitude('');
    setFullTank(true);
  };

  const totalLitres = fuelLogs.reduce((s, f) => s + f.litres, 0);
  const totalCost = fuelLogs.reduce((s, f) => s + f.totalCostZar, 0);
  const avgCostPerLitre = totalLitres > 0 ? totalCost / totalLitres : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      <ErrorBanner message={error} />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Fuel Logs & Diesel Outlay</h1>
          <p className="text-sm text-slate-500 mt-1">Audit fill-ups, station receipts, litre volumes and pump price variations.</p>
        </div>
        <button
          onClick={() => {
            resetForm();
            if (vehicles.length > 0) handleVehicleChange(vehicles[0].vehicleId);
            setIsModalOpen(true);
          }}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Record Fill-Up</span>
        </button>
      </div>

      {/* Fuel Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-slate-200/80 bg-white shadow-sm flex items-center space-x-3">
          <div className="p-3 rounded-lg bg-amber-100 text-amber-700">
            <Droplet className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Total Fuel Volume</p>
            <h3 className="text-2xl font-bold text-slate-900">{totalLitres.toFixed(1)} <span className="text-sm font-normal text-slate-500">Litres</span></h3>
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-200/80 bg-white shadow-sm flex items-center space-x-3">
          <div className="p-3 rounded-lg bg-emerald-100 text-emerald-700">
            <DollarSign className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Total Fuel Spend</p>
            <h3 className="text-2xl font-bold text-slate-900">{formatZAR(totalCost)}</h3>
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-200/80 bg-white shadow-sm flex items-center space-x-3">
          <div className="p-3 rounded-lg bg-blue-100 text-blue-700">
            <Gauge className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Average Pump Rate</p>
            <h3 className="text-2xl font-bold text-slate-900">R {avgCostPerLitre.toFixed(2)} <span className="text-sm font-normal text-slate-500">/ Litre</span></h3>
          </div>
        </div>
      </div>

      {/* Fuel Logs Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-6 py-3.5">Fill Date & Station</th>
                <th className="px-6 py-3.5">Vehicle</th>
                <th className="px-6 py-3.5">Odometer</th>
                <th className="px-6 py-3.5">Volume (L)</th>
                <th className="px-6 py-3.5">Cost / Litre</th>
                <th className="px-6 py-3.5 text-right">Total (ZAR)</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {fuelLogs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-400">
                    No fuel logs recorded yet.
                  </td>
                </tr>
              ) : (
                fuelLogs.map((f) => {
                  const v = vehicles.find((item) => item.vehicleId === f.vehicleId);

                  return (
                    <tr key={f.logId} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{f.stationName || 'Depot Pump'}</div>
                        <div className="text-xs text-slate-500">{formatDateTimeSA(f.fillDate)}</div>
                      </td>
                      <td className="px-6 py-4 font-mono font-medium text-slate-900">
                        {v ? `${v.plateNumber} (${v.model})` : 'Vehicle'}
                      </td>
                      <td className="px-6 py-4 font-medium text-slate-800">
                        {formatKm(f.odometerKm)}
                      </td>
                      <td className="px-6 py-4 font-bold text-slate-900">
                        {f.litres.toFixed(1)} L
                      </td>
                      <td className="px-6 py-4 text-xs font-semibold text-slate-600">
                        R {f.costPerLitreZar.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right font-extrabold text-slate-900">
                        {formatZAR(f.totalCostZar)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleDelete(f.logId)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                          title="Delete fuel log"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Fuel Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Record Fuel Fill-Up">
        <form onSubmit={handleCreate} className="space-y-4">
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
                    {v.plateNumber} ({v.make} {v.model})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Driver (Optional)</label>
              <select
                value={driverId}
                onChange={(e) => setDriverId(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="">Depot / Float Driver</option>
                {drivers.map((d) => (
                  <option key={d.driverId} value={d.driverId}>
                    {d.fullName}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Filling Station Name (optional)</label>
            <input
              type="text"
              placeholder="e.g. Shell Ultra City Harrismith (optional)"
              value={stationName}
              onChange={(e) => setStationName(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Fill Date & Time</label>
              <input
                type="datetime-local"
                required
                value={fillDate}
                onChange={(e) => setFillDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Current Odometer (km)</label>
              <input
                type="number"
                required
                min={0}
                value={odometer}
                onChange={(e) => setOdometer(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Litres (L)</label>
              <input
                type="number"
                step="0.1"
                required
                min={1}
                value={litres}
                onChange={(e) => setLitres(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Cost Per Litre (ZAR)</label>
              <input
                type="number"
                step="0.01"
                required
                min={0.1}
                value={costPerLitre}
                onChange={(e) => setCostPerLitre(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="fuel-lat" className="block text-xs font-semibold text-slate-700 mb-1">Latitude</label>
              <input id="fuel-lat" type="number" step="any" required min={-90} max={90} value={latitude} onChange={(e) => setLatitude(e.target.value)} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none" />
            </div>
            <div>
              <label htmlFor="fuel-lon" className="block text-xs font-semibold text-slate-700 mb-1">Longitude</label>
              <input id="fuel-lon" type="number" step="any" required min={-180} max={180} value={longitude} onChange={(e) => setLongitude(e.target.value)} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none" />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <button type="button" onClick={useMyLocation} disabled={locating} className="text-xs font-semibold text-emerald-700 hover:underline disabled:opacity-60">
              {locating ? 'Locating...' : 'Use my current location'}
            </button>
            <label className="flex items-center space-x-2 text-xs font-semibold text-slate-700">
              <input type="checkbox" checked={fullTank} onChange={(e) => setFullTank(e.target.checked)} />
              <span>Tank filled completely (needed for L/100km)</span>
            </label>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg text-xs flex justify-between font-semibold">
            <span className="text-slate-600">Calculated Total Spend:</span>
            <span className="text-slate-900">{formatZAR(litres * costPerLitre)}</span>
          </div>
          <div className="pt-2 flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              Save Transaction
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
