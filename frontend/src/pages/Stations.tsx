import React, { useEffect, useState } from 'react';
import { MapPin, Plus, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { Station } from '../types';
import { Modal } from '../components/Modal';
import { useAsync } from '../hooks/useAsync';

export const Stations: React.FC = () => {
  const { run, error, busy } = useAsync();
  const [stations, setStations] = useState<Station[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [radiusKm, setRadiusKm] = useState('2');

  const load = () => run(async () => setStations(await api.getStations()));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(async () => {
      await api.createStation({ name, latitude: Number(latitude), longitude: Number(longitude), radiusKm: Number(radiusKm) });
    });
    if (ok) {
      setIsOpen(false);
      setName('');
      setLatitude('');
      setLongitude('');
      await load();
    }
  };

  const remove = async (id: string) => {
    if (confirm('Remove this authorised station? Future fill-ups here will be flagged as outside authorised stations.')) {
      if (await run(() => api.deleteStation(id))) await load();
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Authorised Fuel Stations</h1>
          <p className="text-sm text-slate-500 mt-1">Fill-ups outside these geofences are flagged for review. Without stations, nothing can be verified.</p>
        </div>
        <button onClick={() => setIsOpen(true)} className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm">
          <Plus className="w-4 h-4" />
          <span>Add Station</span>
        </button>
      </div>

      {error && <p role="alert" className="text-sm rounded-lg bg-rose-50 text-rose-800 border border-rose-200 px-3 py-2">{error}</p>}

      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-700">
          <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
            <tr>
              <th className="px-6 py-3.5">Station</th>
              <th className="px-6 py-3.5">Coordinates</th>
              <th className="px-6 py-3.5">Radius</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {stations.length === 0 ? (
              <tr><td colSpan={4} className="px-6 py-8 text-center text-slate-400">No authorised stations configured yet.</td></tr>
            ) : (
              stations.map((s) => (
                <tr key={s.stationId}>
                  <td className="px-6 py-4 font-semibold text-slate-900 flex items-center space-x-2"><MapPin className="w-4 h-4 text-blue-600" /><span>{s.name}</span></td>
                  <td className="px-6 py-4 font-mono text-xs">{s.latitude.toFixed(5)}, {s.longitude.toFixed(5)}</td>
                  <td className="px-6 py-4">{s.radiusKm} km</td>
                  <td className="px-6 py-4 text-right">
                    <button onClick={() => remove(s.stationId)} aria-label={`Remove ${s.name}`} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50"><Trash2 className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Add Authorised Station">
        <form onSubmit={create} className="space-y-4">
          <div>
            <label htmlFor="st-name" className="block text-xs font-semibold text-slate-700 mb-1">Station name</label>
            <input id="st-name" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="st-lat" className="block text-xs font-semibold text-slate-700 mb-1">Latitude</label>
              <input id="st-lat" required type="number" step="any" min={-90} max={90} value={latitude} onChange={(e) => setLatitude(e.target.value)} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200" />
            </div>
            <div>
              <label htmlFor="st-lon" className="block text-xs font-semibold text-slate-700 mb-1">Longitude</label>
              <input id="st-lon" required type="number" step="any" min={-180} max={180} value={longitude} onChange={(e) => setLongitude(e.target.value)} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200" />
            </div>
            <div>
              <label htmlFor="st-rad" className="block text-xs font-semibold text-slate-700 mb-1">Radius (km)</label>
              <input id="st-rad" required type="number" step="0.1" min={0.1} max={10} value={radiusKm} onChange={(e) => setRadiusKm(e.target.value)} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200" />
            </div>
          </div>
          <div className="pt-2 flex justify-end space-x-2">
            <button type="button" onClick={() => setIsOpen(false)} className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600">Cancel</button>
            <button type="submit" disabled={busy} className="px-4 py-2 text-sm rounded-lg bg-emerald-600 text-white font-semibold disabled:opacity-60">Save station</button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
