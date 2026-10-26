import React, { useEffect, useState } from 'react';
import { Plus, Phone, ShieldCheck, Trash2, Edit2 } from 'lucide-react';
import { api } from '../services/api';
import { Driver, DriverStatus, Vehicle } from '../types';
import { formatDateSA } from '../utils/format';
import { Modal } from '../components/Modal';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Drivers: React.FC = () => {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedDriver, setSelectedDriver] = useState<Driver | null>(null);

  // Form State
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('+27');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [licenseExpiryDate, setLicenseExpiryDate] = useState('2028-01-01');
  const [prdpExpiryDate, setPrdpExpiryDate] = useState('2027-01-01');
  const [assignedVehicleId, setAssignedVehicleId] = useState('');
  const [status, setStatus] = useState<DriverStatus>('AVAILABLE');

  const { run, error } = useAsync();

  const loadData = async () => {
    await run(async () => {
      const [dList, vList] = await Promise.all([api.getDrivers(), api.getVehicles()]);
      setDrivers(dList);
      setVehicles(vList);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() =>
      api.createDriver({
        fullName,
        phone: phone.replace(/\s+/g, ''),
        licenseNumber,
        licenseExpiryDate,
        prdpExpiryDate: prdpExpiryDate || undefined,
        assignedVehicleId: assignedVehicleId || undefined,
      }),
    );
    if (!ok) return;
    setIsAddModalOpen(false);
    resetForm();
    await loadData();
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDriver) return;
    // ON_TRIP is owned by the trip workflow and cannot be set here.
    const ok = await run(() =>
      api.updateDriver(selectedDriver.driverId, {
        phone: phone.replace(/\s+/g, ''),
        ...(status === 'AVAILABLE' || status === 'OFF_DUTY' ? { status } : {}),
        assignedVehicleId: assignedVehicleId || undefined,
        prdpExpiryDate: prdpExpiryDate || undefined,
      }),
    );
    if (!ok) return;
    setIsEditModalOpen(false);
    setSelectedDriver(null);
    await loadData();
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to remove this driver profile?')) {
      if (await run(() => api.deleteDriver(id))) await loadData();
    }
  };

  const openEdit = (d: Driver) => {
    setSelectedDriver(d);
    setPhone(d.phone);
    setStatus(d.status);
    setAssignedVehicleId(d.assignedVehicleId || '');
    setPrdpExpiryDate(d.prdpExpiryDate || '');
    setIsEditModalOpen(true);
  };

  const resetForm = () => {
    setFullName('');
    setPhone('+27');
    setLicenseNumber('');
    setLicenseExpiryDate('2028-01-01');
    setPrdpExpiryDate('2027-01-01');
    setAssignedVehicleId('');
    setStatus('AVAILABLE');
  };

  // Helper to check PrDP validity
  const getPrdpStatus = (dateStr?: string) => {
    if (!dateStr) return { label: 'No PrDP', color: 'bg-slate-100 text-slate-600' };
    const today = new Date().toISOString().slice(0, 10);
    if (dateStr < today) {
      return { label: 'PrDP Expired', color: 'bg-rose-100 text-rose-800 font-bold' };
    }
    const daysRemaining = (new Date(dateStr).getTime() - new Date().getTime()) / (1000 * 3600 * 24);
    if (daysRemaining < 60) {
      return { label: 'Expires Soon', color: 'bg-amber-100 text-amber-800' };
    }
    return { label: 'Valid PrDP', color: 'bg-emerald-100 text-emerald-800' };
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <ErrorBanner message={error} />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Driver Management</h1>
          <p className="text-sm text-slate-500 mt-1">Track professional drivers, South African PrDP permits, and duty assignments.</p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setIsAddModalOpen(true);
          }}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Add Driver</span>
        </button>
      </div>

      {/* Drivers List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {drivers.map((d) => {
          const prdp = getPrdpStatus(d.prdpExpiryDate);
          const assignedV = vehicles.find((v) => v.vehicleId === d.assignedVehicleId);

          return (
            <div
              key={d.driverId}
              className="p-5 bg-white rounded-xl border border-slate-200/80 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{d.fullName}</h3>
                    <div className="flex items-center space-x-1.5 text-xs text-slate-500 mt-0.5">
                      <Phone className="w-3.5 h-3.5" />
                      <span>{d.phone}</span>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                      d.status === 'AVAILABLE'
                        ? 'bg-emerald-100 text-emerald-800'
                        : d.status === 'ON_TRIP'
                        ? 'bg-blue-100 text-blue-800 animate-pulse'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {d.status.replace('_', ' ')}
                  </span>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-slate-100 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">License Number:</span>
                    <span className="font-mono font-medium text-slate-800">{d.licenseNumber}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">License Expiry:</span>
                    <span className="text-slate-800">{formatDateSA(d.licenseExpiryDate)}</span>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-slate-500 flex items-center space-x-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                      <span>PrDP Permit:</span>
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs ${prdp.color}`}>
                      {prdp.label} ({formatDateSA(d.prdpExpiryDate)})
                    </span>
                  </div>
                  <div className="flex justify-between pt-1">
                    <span className="text-slate-500">Assigned Vehicle:</span>
                    <span className="font-medium text-slate-800">
                      {assignedV ? `${assignedV.plateNumber} (${assignedV.make})` : 'Unassigned'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-end space-x-2 mt-4">
                <button
                  onClick={() => openEdit(d)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition-colors"
                  title="Edit driver"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(d.driverId)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                  title="Remove driver"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Add Driver Modal */}
      <Modal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} title="Register Driver">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Full Legal Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Sipho Dlamini"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number (SA Format)</label>
            <input
              type="text"
              required
              placeholder="+27 82 123 4567"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">License Number</label>
              <input
                type="text"
                required
                placeholder="ZA..."
                value={licenseNumber}
                onChange={(e) => setLicenseNumber(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">License Expiry Date</label>
              <input
                type="date"
                required
                value={licenseExpiryDate}
                onChange={(e) => setLicenseExpiryDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">PrDP Permit Expiry</label>
              <input
                type="date"
                value={prdpExpiryDate}
                onChange={(e) => setPrdpExpiryDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Assigned Vehicle</label>
              <select
                value={assignedVehicleId}
                onChange={(e) => setAssignedVehicleId(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="">None (Floating Driver)</option>
                {vehicles.map((v) => (
                  <option key={v.vehicleId} value={v.vehicleId}>
                    {v.plateNumber} ({v.make} {v.model})
                  </option>
                ))}
              </select>
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
              Save Driver
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit Driver Modal */}
      <Modal isOpen={isEditModalOpen} onClose={() => setIsEditModalOpen(false)} title={`Update ${selectedDriver?.fullName}`}>
        <form onSubmit={handleUpdate} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number</label>
            <input
              type="text"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">PrDP Permit Expiry Date</label>
            <input
              type="date"
              value={prdpExpiryDate}
              onChange={(e) => setPrdpExpiryDate(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Duty Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as DriverStatus)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
            >
              <option value="AVAILABLE">Available</option>
              <option value="ON_TRIP">On Trip</option>
              <option value="OFF_DUTY">Off Duty</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Assigned Vehicle</label>
            <select
              value={assignedVehicleId}
              onChange={(e) => setAssignedVehicleId(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
            >
              <option value="">None (Floating Driver)</option>
              {vehicles.map((v) => (
                <option key={v.vehicleId} value={v.vehicleId}>
                  {v.plateNumber} ({v.make} {v.model})
                </option>
              ))}
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
              Save Changes
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
