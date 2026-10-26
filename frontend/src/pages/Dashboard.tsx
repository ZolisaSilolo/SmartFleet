import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Truck,
  Navigation,
  Fuel,
  Wrench,
  ArrowRight,
  TrendingUp,
  Coins,
  ShieldAlert,
  Bot,
} from 'lucide-react';

import { api } from '../services/api';
import { DashboardStats, Trip } from '../types';
import { formatZAR, formatKm, formatDateSA } from '../utils/format';
import { StatCard } from '../components/StatCard';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentTrips, setRecentTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);

  const { run, error } = useAsync();

  useEffect(() => {
    async function loadData() {
      await run(async () => {
        const [dashStats, trips] = await Promise.all([api.getDashboard(), api.getTrips()]);
        setStats(dashStats);
        setRecentTrips(trips.slice(0, 5));
      });
      setLoading(false);
    }
    void loadData();
  }, [run]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  if (!stats) {
    return <ErrorBanner message={error ?? 'The dashboard could not be loaded.'} />;
  }

  const isPositiveCashFlow = stats.netOperationalCashFlowZar >= 0;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Top Welcome & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Fleet & Cash-Flow Overview
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time South African SME operational tracking and financial metrics.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Link
            to="/trips"
            className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"
          >
            <Navigation className="w-4 h-4" />
            <span>New Trip</span>
          </Link>
          <Link
            to="/fuel"
            className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-semibold bg-slate-900 hover:bg-slate-800 text-white shadow-sm transition-all"
          >
            <Fuel className="w-4 h-4" />
            <span>Log Fuel</span>
          </Link>
          <Link
            to="/analytics?tab=agent"
            className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-all"
          >
            <Bot className="w-4 h-4" />
            <span>AI Dispatcher</span>
          </Link>

        </div>
      </div>

      {/* Critical Overdue Alerts Banner */}
      {stats.overdueMaintenanceCount > 0 && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200/80 shadow-sm flex items-start justify-between gap-4">
          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-amber-100 text-amber-700 mt-0.5">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-amber-900">
                Action Required: {stats.overdueMaintenanceCount} Maintenance Alert{stats.overdueMaintenanceCount > 1 ? 's' : ''} Due
              </h4>
              <ul className="text-xs text-amber-800 mt-1 space-y-1 list-disc list-inside">
                {stats.overdueAlerts.map((alert, idx) => (
                  <li key={idx}>
                    <span className="font-semibold">{alert.plateNumber}:</span> {alert.reason}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <Link
            to="/maintenance"
            className="text-xs font-bold text-amber-900 hover:text-amber-950 underline flex items-center space-x-1 shrink-0"
          >
            <span>Resolve</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Primary KPI Stat Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Net Operational Cash Flow"
          value={formatZAR(stats.netOperationalCashFlowZar)}
          icon={Coins}
          subtext={`Revenue - (Fuel + Maint)`}
          color={isPositiveCashFlow ? 'green' : 'red'}
        />
        <StatCard
          title="MTD Revenue"
          value={formatZAR(stats.mtdRevenueZar)}
          icon={TrendingUp}
          subtext="Completed freight billing"
          color="blue"
        />
        <StatCard
          title="MTD Fuel Spend"
          value={formatZAR(stats.mtdFuelSpendZar)}
          icon={Fuel}
          subtext="Diesel & petrol outlay"
          color="amber"
        />
        <StatCard
          title="MTD Maintenance Spend"
          value={formatZAR(stats.mtdMaintenanceSpendZar)}
          icon={Wrench}
          subtext="Depot & workshop services"
          color="purple"
        />
      </div>

      {/* Fleet Operational Status */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-slate-200/80 bg-white shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-emerald-100 text-emerald-700">
              <Truck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Active Fleet</p>
              <h4 className="text-xl font-bold text-slate-900">
                {stats.activeVehiclesCount} <span className="text-xs font-normal text-slate-500">/ {stats.totalVehiclesCount} total</span>
              </h4>
            </div>
          </div>
          <Link to="/vehicles" className="text-xs font-medium text-emerald-600 hover:underline">
            View
          </Link>
        </div>

        <div className="p-4 rounded-xl border border-slate-200/80 bg-white shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-blue-100 text-blue-700">
              <Navigation className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Trips In Transit</p>
              <h4 className="text-xl font-bold text-slate-900">{stats.activeTripsCount} Trips</h4>
            </div>
          </div>
          <Link to="/trips" className="text-xs font-medium text-blue-600 hover:underline">
            View
          </Link>
        </div>

        <div className="p-4 rounded-xl border border-slate-200/80 bg-white shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-purple-100 text-purple-700">
              <Truck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Available Drivers</p>
              <h4 className="text-xl font-bold text-slate-900">{stats.availableDriversCount} Ready</h4>
            </div>
          </div>
          <Link to="/drivers" className="text-xs font-medium text-purple-600 hover:underline">
            View
          </Link>
        </div>
      </div>

      {/* Recent Trips Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">Recent Transport Dispatches</h3>
            <p className="text-xs text-slate-500">Latest corridor trips across South Africa</p>
          </div>
          <Link to="/trips" className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center space-x-1">
            <span>All Trips</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50/75 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-6 py-3">Route</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3">Distance</th>
                <th className="px-6 py-3 text-right">Revenue (ZAR)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentTrips.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    No trips logged yet. Start a new trip above.
                  </td>
                </tr>
              ) : (
                recentTrips.map((trip) => (
                  <tr key={trip.tripId} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-3.5 font-medium text-slate-900">
                      <div>{trip.origin}</div>
                      <div className="text-xs text-slate-500">➔ {trip.destination}</div>
                    </td>
                    <td className="px-6 py-3.5">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                          trip.status === 'COMPLETED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : trip.status === 'IN_PROGRESS'
                            ? 'bg-blue-100 text-blue-800 animate-pulse'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {trip.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 text-xs text-slate-500">
                      {formatDateSA(trip.startTime)}
                    </td>
                    <td className="px-6 py-3.5 text-xs text-slate-700">
                      {trip.distanceKm ? formatKm(trip.distanceKm) : 'In progress'}
                    </td>
                    <td className="px-6 py-3.5 text-right font-semibold text-slate-900">
                      {formatZAR(trip.revenueZar || 0)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
