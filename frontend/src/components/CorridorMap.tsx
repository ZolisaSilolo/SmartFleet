import React, { useEffect, useState } from 'react';
import { MapPin, Navigation, ShieldCheck, ShieldAlert, Fuel, Info } from 'lucide-react';
import { api } from '../services/api';
import { CorridorReference, GeofenceCheck, RoutePlan, Station } from '../types';
import { formatZAR, formatKm } from '../utils/format';
import { ErrorBanner } from './ErrorBanner';
import { useAsync } from '../hooks/useAsync';

/**
 * Corridor reference data and fuel geofence verification. Everything shown comes from the API:
 * corridor data is labelled reference data (not live Sanral data) and geofences are the fleet's own stations.
 */
export const CorridorMap: React.FC = () => {
  const { run, error } = useAsync();
  const [reference, setReference] = useState<CorridorReference | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [plan, setPlan] = useState<RoutePlan | null>(null);
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [check, setCheck] = useState<GeofenceCheck | null>(null);

  useEffect(() => {
    void run(async () => {
      const [ref, st] = await Promise.all([api.getCorridors(), api.getStations()]);
      setReference(ref);
      setStations(st);
      const keys = Object.keys(ref.hubs);
      setOrigin(keys[0] ?? '');
      setDestination(keys[1] ?? '');
    });
  }, [run]);

  const planRoute = async (e: React.FormEvent) => {
    e.preventDefault();
    setPlan(null);
    await run(async () => setPlan(await api.planRoute(origin, destination)));
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setCheck(null);
    await run(async () => setCheck(await api.verifyFuelLocation(Number(lat), Number(lon))));
  };

  const hubs = reference ? Object.entries(reference.hubs) : [];
  const selectClass = 'w-full px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none';

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={planRoute} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4" aria-label="Corridor lookup">
          <h3 className="font-bold text-slate-900 flex items-center space-x-2"><Navigation className="w-4 h-4 text-blue-600" /><span>Corridor lookup</span></h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="origin" className="block text-xs font-semibold text-slate-700 mb-1">Origin hub</label>
              <select id="origin" value={origin} onChange={(e) => setOrigin(e.target.value)} className={selectClass}>
                {hubs.map(([key, hub]) => <option key={key} value={key}>{hub.name}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="destination" className="block text-xs font-semibold text-slate-700 mb-1">Destination hub</label>
              <select id="destination" value={destination} onChange={(e) => setDestination(e.target.value)} className={selectClass}>
                {hubs.map(([key, hub]) => <option key={key} value={key}>{hub.name}</option>)}
              </select>
            </div>
          </div>
          <button type="submit" className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold">Look up corridor</button>

          {plan && (
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4 text-sm space-y-2" data-testid="route-plan">
              <p className="font-bold text-slate-900">{plan.corridor}</p>
              <p>{formatKm(plan.distanceKm)} &bull; about {plan.estimatedDriveHours} h &bull; Class 2 toll {formatZAR(plan.tollCostZar)}</p>
              <p className="text-xs text-slate-600">Toll plazas: {plan.tollPlazas.join(', ')}</p>
              <p className="text-xs text-slate-600 flex items-center space-x-1"><Fuel className="w-3 h-3" /><span>Suggested fuel stop: {plan.suggestedFuelStop}</span></p>
              <p className="text-[11px] text-slate-500 flex items-start space-x-1"><Info className="w-3 h-3 mt-0.5 shrink-0" /><span>{plan.dataSource}. Confirm tariffs with Sanral before quoting.</span></p>
            </div>
          )}
        </form>

        <form onSubmit={verify} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4" aria-label="Fill-up location check">
          <h3 className="font-bold text-slate-900 flex items-center space-x-2"><MapPin className="w-4 h-4 text-amber-600" /><span>Fill-up location check</span></h3>
          <p className="text-xs text-slate-500">Checks coordinates against your {stations.length} authorised station{stations.length === 1 ? '' : 's'}.</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="chk-lat" className="block text-xs font-semibold text-slate-700 mb-1">Latitude</label>
              <input id="chk-lat" type="number" step="any" required min={-90} max={90} value={lat} onChange={(e) => setLat(e.target.value)} className={selectClass} />
            </div>
            <div>
              <label htmlFor="chk-lon" className="block text-xs font-semibold text-slate-700 mb-1">Longitude</label>
              <input id="chk-lon" type="number" step="any" required min={-180} max={180} value={lon} onChange={(e) => setLon(e.target.value)} className={selectClass} />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 text-sm rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold">Check location</button>

          {check && (
            <div
              role="status"
              className={`rounded-lg border p-4 text-sm flex items-start space-x-2 ${
                check.status === 'AUTHORIZED'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                  : check.status === 'OUTSIDE_AUTHORIZED'
                  ? 'border-rose-200 bg-rose-50 text-rose-900'
                  : 'border-slate-200 bg-slate-50 text-slate-700'
              }`}
            >
              {check.status === 'AUTHORIZED' ? <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" /> : <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />}
              <span>{check.message}</span>
            </div>
          )}
        </form>
      </div>

      {reference && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr><th className="px-6 py-3">Corridor</th><th className="px-6 py-3">Distance</th><th className="px-6 py-3">Drive time</th><th className="px-6 py-3 text-right">Class 2 toll</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reference.corridors.map((c) => (
                <tr key={c.corridorId}>
                  <td className="px-6 py-3 font-semibold text-slate-900">{c.corridor}</td>
                  <td className="px-6 py-3">{formatKm(c.distanceKm)}</td>
                  <td className="px-6 py-3">{c.estimatedDriveHours} h</td>
                  <td className="px-6 py-3 text-right font-semibold">{formatZAR(c.tollCostZarClass2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-6 py-2 text-[11px] text-slate-500 border-t border-slate-100">{reference.dataSource}</p>
        </div>
      )}
    </div>
  );
};
