import React, { useEffect, useState } from 'react';
import { Plus, Search, Filter, Trash2, Edit2 } from 'lucide-react';
import { api } from '../services/api';
import { Vehicle, VehicleStatus, FuelType } from '../types';
import { formatKm, formatLPer100Km } from '../utils/format';
import { Modal } from '../components/Modal';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Vehicles: React.FC = () => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedVehicle, setSelectedVehicle] = useState<Vehicle | null>(null);

  // Form State
  const [plateNumber, setPlateNumber] = useState('');
  const [make, setMake] = useState('Toyota');
  const [model, setModel] = useState('');
  const [year, setYear] = useState(2022);
  const [fuelType, setFuelType] = useState<FuelType>('DIESEL');
  const [odometer, setOdometer] = useState(50000);
  const [targetEff, setTargetEff] = useState(10.0);
  const [status, setStatus] = useState<VehicleStatus>('ACTIVE');

  const { run, error } = useAsync();

  const loadVehicles = async () => {
    await run(async () => setVehicles(await api.getVehicles()));
  };

  useEffect(() => {
    loadVehicles();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() =>
      api.createVehicle({
        plateNumber,
        make,
        model,
        year: Number(year),
        fuelType,
        currentOdometerKm: Number(odometer),
        targetEfficiencyLPer100Km: Number(targetEff),
      }),
    );
    if (!ok) return;
    setIsAddModalOpen(false);
    resetForm();
    await loadVehicles();
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVehicle) return;
    // IN_MAINTENANCE is owned by the maintenance workflow and cannot be set here.
    const ok = await run(() =>
      api.updateVehicle(selectedVehicle.vehicleId, {
        currentOdometerKm: Number(odometer),
        targetEfficiencyLPer100Km: Number(targetEff),
        ...(status === 'ACTIVE' || status === 'INACTIVE' ? { status } : {}),
      }),
    );
    if (!ok) return;
    setIsEditModalOpen(false);
    setSelectedVehicle(null);
    await loadVehicles();
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this vehicle from your fleet?')) {
      if (await run(() => api.deleteVehicle(id))) await loadVehicles();
    }
  };

  const openEdit = (v: Vehicle) => {
    setSelectedVehicle(v);
    setOdometer(v.currentOdometerKm);
    setTargetEff(v.targetEfficiencyLPer100Km);
    setStatus(v.status);
    setIsEditModalOpen(true);
  };

  const resetForm = () => {
    setPlateNumber('');
    setMake('Toyota');
    setModel('');
    setYear(2022);
    setFuelType('DIESEL');
    setOdometer(50000);
    setTargetEff(10.0);
    setStatus('ACTIVE');
  };

  const filtered = vehicles.filter((v) => {
    const matchesSearch =
      v.plateNumber.toLowerCase().includes(search.toLowerCase()) ||
      v.make.toLowerCase().includes(search.toLowerCase()) ||
      v.model.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || v.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <ErrorBanner message={error} />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Fleet Vehicles</h1>
          <p className="text-sm text-slate-500 mt-1">Manage registration plates, models, odometers and target L/100km.</p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setIsAddModalOpen(true);
          }}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Add Vehicle</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="p-4 bg-white rounded-xl border border-slate-200/80 shadow-sm flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search by SA registration plate, make, or model..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="py-2 pl-3 pr-8 text-sm rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="IN_MAINTENANCE">In Maintenance</option>
            <option value="INACTIVE">Inactive</option>
          </select>
        </div>
      </div>

      {/* Vehicles Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-6 py-3.5">Registration Plate</th>
                <th className="px-6 py-3.5">Vehicle Spec</th>
                <th className="px-6 py-3.5">Odometer</th>
                <th className="px-6 py-3.5">Target Efficiency</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                    No vehicles found matching your criteria.
                  </td>
                </tr>
              ) : (
                filtered.map((v) => (
                  <tr key={v.vehicleId} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4 font-mono font-bold text-slate-900">
                      <span className="px-2.5 py-1 bg-slate-100 border border-slate-300 rounded text-xs font-semibold">
                        {v.plateNumber}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{v.make} {v.model}</div>
                      <div className="text-xs text-slate-500">{v.year} • {v.fuelType}</div>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-900">
                      {formatKm(v.currentOdometerKm)}
                    </td>
                    <td className="px-6 py-4 text-xs font-medium text-slate-600">
                      {formatLPer100Km(v.targetEfficiencyLPer100Km)}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          v.status === 'ACTIVE'
                            ? 'bg-emerald-100 text-emerald-800'
                            : v.status === 'IN_MAINTENANCE'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {v.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => openEdit(v)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition-colors"
                        title="Update Odometer & Status"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(v.vehicleId)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        title="Delete vehicle"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Vehicle Modal */}
      <Modal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} title="Register Fleet Vehicle">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Registration Plate (SA format)</label>
            <input
              type="text"
              required
              placeholder="e.g. CA 123-456 or GP 99 XX GP"
              value={plateNumber}
              onChange={(e) => setPlateNumber(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Make</label>
              <input
                type="text"
                required
                placeholder="Toyota, Isuzu, etc."
                value={make}
                onChange={(e) => setMake(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Model</label>
              <input
                type="text"
                required
                placeholder="Quantum, NPR 400, etc."
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Year</label>
              <input
                type="number"
                required
                min={1995}
                max={2030}
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Fuel Type</label>
              <select
                value={fuelType}
                onChange={(e) => setFuelType(e.target.value as FuelType)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="DIESEL">Diesel</option>
                <option value="PETROL">Petrol</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
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
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Target L/100km</label>
              <input
                type="number"
                step="0.1"
                required
                min={1}
                value={targetEff}
                onChange={(e) => setTargetEff(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="pt-2 flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              Save Vehicle
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit Vehicle Modal */}
      <Modal isOpen={isEditModalOpen} onClose={() => setIsEditModalOpen(false)} title={`Update ${selectedVehicle?.plateNumber}`}>
        <form onSubmit={handleUpdate} className="space-y-4">
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
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Target Efficiency (L/100km)</label>
            <input
              type="number"
              step="0.1"
              required
              min={1}
              value={targetEff}
              onChange={(e) => setTargetEff(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Operational Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as VehicleStatus)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
            >
              <option value="ACTIVE">Active</option>
              <option value="IN_MAINTENANCE">In Maintenance</option>
              <option value="INACTIVE">Inactive</option>
            </select>
          </div>
          <div className="pt-2 flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsEditModalOpen(false)}
              className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              Update Fleet Status
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
