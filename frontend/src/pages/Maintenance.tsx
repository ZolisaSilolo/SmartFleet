import React, { useEffect, useState } from 'react';
import { Wrench, Plus, AlertTriangle, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { MaintenanceRecord, OverdueAlert, ServiceType, UserMaintenanceStatus, Vehicle } from '../types';
import { formatZAR, formatKm, formatDateSA } from '../utils/format';
import { Modal } from '../components/Modal';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Maintenance: React.FC = () => {
  const [records, setRecords] = useState<MaintenanceRecord[]>([]);
  const [dueRecords, setDueRecords] = useState<OverdueAlert[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [activeTab, setActiveTab] = useState<'ALL' | 'DUE'>('ALL');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Form State
  const [vehicleId, setVehicleId] = useState('');
  const [serviceType, setServiceType] = useState<ServiceType>('ROUTINE_SERVICE');
  const [description, setDescription] = useState('');
  const [costZar, setCostZar] = useState(4500);
  const [serviceDate, setServiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [odometerAtService, setOdometerAtService] = useState(50000);
  const [nextDueOdometer, setNextDueOdometer] = useState(65000);
  const [nextDueDate, setNextDueDate] = useState('2027-04-01');
  const [status, setStatus] = useState<UserMaintenanceStatus>('SCHEDULED');
  const { run, error } = useAsync();

  const loadData = async () => {
    await run(async () => {
      const [mList, dList, vList] = await Promise.all([api.getMaintenance(), api.getMaintenanceDue(), api.getVehicles()]);
      setRecords(mList);
      setDueRecords(dList);
      setVehicles(vList);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleVehicleChange = (vId: string) => {
    setVehicleId(vId);
    const v = vehicles.find((item) => item.vehicleId === vId);
    if (v) {
      setOdometerAtService(v.currentOdometerKm);
      setNextDueOdometer(v.currentOdometerKm + 15000);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() =>
      api.createMaintenance({
        vehicleId,
        serviceType,
        description,
        costZar: Number(costZar),
        serviceDate,
        odometerAtServiceKm: Number(odometerAtService),
        nextDueOdometerKm: Number(nextDueOdometer),
        nextDueDate,
        status,
      }),
    );
    if (!ok) return;
    setIsAddModalOpen(false);
    resetForm();
    await loadData();
  };

  const handleUpdateStatus = async (id: string, newStatus: UserMaintenanceStatus) => {
    if (await run(() => api.updateMaintenance(id, { status: newStatus }))) await loadData();
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this maintenance record?')) {
      if (await run(() => api.deleteMaintenance(id))) await loadData();
    }
  };

  const resetForm = () => {
    setVehicleId('');
    setServiceType('ROUTINE_SERVICE');
    setDescription('');
    setCostZar(4500);
    setStatus('SCHEDULED');
  };

  const displayedRecords: MaintenanceRecord[] =
    activeTab === 'DUE'
      ? dueRecords.flatMap((a) => records.filter((r) => r.recordId === a.recordId))
      : records;
  const dueReasonFor = (recordId: string) => dueRecords.find((a) => a.recordId === recordId)?.reason;

  return (
    <div className="space-y-6 animate-fade-in">
      <ErrorBanner message={error} />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Maintenance & Roadworthiness</h1>
          <p className="text-sm text-slate-500 mt-1">Schedule services, heavy vehicle COF inspections, brake overhauls, and tyre replacements.</p>
        </div>
        <button
          onClick={() => {
            resetForm();
            if (vehicles.length > 0) handleVehicleChange(vehicles[0].vehicleId);
            setIsAddModalOpen(true);
          }}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Record Service</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('ALL')}
          className={`py-3 px-4 text-sm font-semibold border-b-2 transition-all flex items-center space-x-2 ${
            activeTab === 'ALL'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Wrench className="w-4 h-4" />
          <span>All Maintenance Logs ({records.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('DUE')}
          className={`py-3 px-4 text-sm font-semibold border-b-2 transition-all flex items-center space-x-2 ${
            activeTab === 'DUE'
              ? 'border-amber-600 text-amber-700 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span>Due & Overdue Alerts ({dueRecords.length})</span>
        </button>
      </div>

      {/* Maintenance Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-6 py-3.5">Service Type & Vehicle</th>
                <th className="px-6 py-3.5">Description</th>
                <th className="px-6 py-3.5">Next Due Criteria</th>
                <th className="px-6 py-3.5">Cost (ZAR)</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedRecords.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                    {activeTab === 'DUE' ? 'No vehicles currently overdue for maintenance.' : 'No maintenance records found.'}
                  </td>
                </tr>
              ) : (
                displayedRecords.map((m) => {
                  const v = vehicles.find((item) => item.vehicleId === m.vehicleId);

                  return (
                    <tr key={m.recordId} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-bold uppercase bg-slate-100 text-slate-700 border border-slate-200 mb-1">
                          {m.serviceType.replace('_', ' ')}
                        </span>
                        <div className="font-semibold text-slate-900 font-mono text-xs">
                          {v?.plateNumber || 'Vehicle'} ({v?.make} {v?.model})
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-900">{m.description}</div>
                        <div className="text-xs text-slate-500">Service Date: {formatDateSA(m.serviceDate)}</div>
                      </td>
                      <td className="px-6 py-4 text-xs">
                        {dueReasonFor(m.recordId) ? (
                          <div className="p-1.5 rounded bg-amber-50 border border-amber-200 text-amber-800 font-semibold">
                            {dueReasonFor(m.recordId)}
                          </div>
                        ) : (
                          <div className="text-slate-600">
                            <div>Due Date: {formatDateSA(m.nextDueDate)}</div>
                            {m.nextDueOdometerKm && <div>Due Odo: {formatKm(m.nextDueOdometerKm)}</div>}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 font-bold text-slate-900">
                        {formatZAR(m.costZar)}
                      </td>
                      <td className="px-6 py-4">
                        {m.status === 'PROPOSED' && (
                          <div className="mb-1 text-[10px] font-bold uppercase text-indigo-700">AI proposal - needs approval</div>
                        )}
                        <select
                          value={m.status}
                          onChange={(e) => handleUpdateStatus(m.recordId, e.target.value as UserMaintenanceStatus)}
                          className={`text-xs font-semibold py-1 px-2.5 rounded-lg border focus:outline-none ${
                            m.status === 'COMPLETED'
                              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                              : m.status === 'IN_PROGRESS'
                              ? 'bg-blue-50 text-blue-800 border-blue-200'
                              : 'bg-amber-50 text-amber-800 border-amber-200'
                          }`}
                        >
                          {m.status === 'PROPOSED' && <option value="PROPOSED" disabled>Proposed (approve by scheduling)</option>}
                          <option value="SCHEDULED">{m.status === 'PROPOSED' ? 'Approve & schedule' : 'Scheduled'}</option>
                          <option value="IN_PROGRESS">In Progress</option>
                          <option value="COMPLETED">Completed</option>
                        </select>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleDelete(m.recordId)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                          title="Delete record"
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

      {/* Add Maintenance Modal */}
      <Modal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} title="Record Vehicle Maintenance">
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
              <label className="block text-xs font-semibold text-slate-700 mb-1">Service Type</label>
              <select
                value={serviceType}
                onChange={(e) => setServiceType(e.target.value as ServiceType)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="ROUTINE_SERVICE">Routine Major/Minor Service</option>
                <option value="TYRES">Tyre Replacement / Balancing</option>
                <option value="BRAKES">Brakes Discs & Pads</option>
                <option value="ENGINE_REPAIR">Engine & Transmission Repair</option>
                <option value="COF_INSPECTION">Heavy Vehicle COF Roadworthy</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Service Description / Workshop Details</label>
            <input
              type="text"
              required
              placeholder="e.g. 150,000km Major Service with diesel filter & oil change"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Total Cost (ZAR)</label>
              <input
                type="number"
                required
                min={0}
                value={costZar}
                onChange={(e) => setCostZar(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Service Date</label>
              <input
                type="date"
                required
                value={serviceDate}
                onChange={(e) => setServiceDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Odometer at Service (km)</label>
              <input
                type="number"
                required
                min={0}
                value={odometerAtService}
                onChange={(e) => setOdometerAtService(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Next Due Odometer (km)</label>
              <input
                type="number"
                min={0}
                value={nextDueOdometer}
                onChange={(e) => setNextDueOdometer(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Next Due Date (Target)</label>
              <input
                type="date"
                value={nextDueDate}
                onChange={(e) => setNextDueDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Initial Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as UserMaintenanceStatus)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
              >
                <option value="SCHEDULED">Scheduled</option>
                <option value="IN_PROGRESS">In Progress (Depot Workshop)</option>
                <option value="COMPLETED">Completed</option>
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
              Save Service Record
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
