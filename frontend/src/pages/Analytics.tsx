import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Coins,
  Bot,
  MapPin,
  BarChart3,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import { CostBreakdown, EfficiencyMetric, UtilisationMetric, AiInsightsResponse } from '../types';
import { formatZAR, formatKm, formatLPer100Km, formatRandPerKm } from '../utils/format';
import { CorridorMap } from '../components/CorridorMap';
import { AgentConsole } from '../components/AgentConsole';
import { ErrorBanner } from '../components/ErrorBanner';
import { useAsync } from '../hooks/useAsync';

export const Analytics: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'agent';
  const [activeTab, setActiveTab] = useState<'agent' | 'corridors' | 'metrics' | 'all'>(
    (initialTab as any) || 'agent'
  );

  const [costs, setCosts] = useState<CostBreakdown[]>([]);
  const [efficiency, setEfficiency] = useState<EfficiencyMetric[]>([]);
  const [utilisation, setUtilisation] = useState<UtilisationMetric[]>([]);
  const [windowDays, setWindowDays] = useState(365);
  const [insights, setInsights] = useState<AiInsightsResponse | null>(null);
  const dataState = useAsync();
  const aiState = useAsync();
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [loadingData, setLoadingData] = useState(true);

  const handleTabChange = (tab: 'agent' | 'corridors' | 'metrics' | 'all') => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  useEffect(() => {
    async function loadAllAnalytics() {
      await dataState.run(async () => {
        const [c, e, u] = await Promise.all([api.getCosts(), api.getEfficiency(), api.getUtilisation()]);
        setCosts(c.items);
        setWindowDays(c.windowDays);
        setEfficiency(e.items);
        setUtilisation(u.items);
      });
      setLoadingData(false);
    }
    loadAllAnalytics();
  }, []);

  const fetchAiInsights = async () => {
    setLoadingInsights(true);
    setInsights(null);
    await aiState.run(async () => setInsights(await api.getAiInsights()));
    setLoadingInsights(false);
  };

  useEffect(() => {
    fetchAiInsights();
  }, []);

  if (loadingData) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <ErrorBanner message={dataState.error} />
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Financial & Fleet Intelligence
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            AI assistant &bull; Corridor reference data &bull; Fuel anomaly detection &bull; Cost per kilometre (last {windowDays} days)
          </p>
        </div>
        <button
          onClick={fetchAiInsights}
          disabled={loadingInsights}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white shadow-md shadow-emerald-500/20 transition-all disabled:opacity-50"
        >
          {loadingInsights ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          <span>Refresh AI Insights</span>
        </button>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center space-x-2 p-1.5 bg-slate-200/60 rounded-xl overflow-x-auto">
        <button
          onClick={() => handleTabChange('agent')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs md:text-sm font-semibold transition ${
            activeTab === 'agent'
              ? 'bg-white text-indigo-700 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
          }`}
        >
          <Bot className="w-4 h-4 text-indigo-600" />
          <span>Autonomous Agent</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] bg-indigo-100 text-indigo-700 font-mono">Bedrock</span>
        </button>

        <button
          onClick={() => handleTabChange('corridors')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs md:text-sm font-semibold transition ${
            activeTab === 'corridors'
              ? 'bg-white text-blue-700 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
          }`}
        >
          <MapPin className="w-4 h-4 text-blue-600" />
          <span>Corridors & Tolls</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] bg-blue-100 text-blue-700 font-mono">Geofence</span>
        </button>

        <button
          onClick={() => handleTabChange('metrics')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs md:text-sm font-semibold transition ${
            activeTab === 'metrics'
              ? 'bg-white text-emerald-700 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
          }`}
        >
          <BarChart3 className="w-4 h-4 text-emerald-600" />
          <span>Financials & Anomalies</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-100 text-emerald-700 font-mono">R/km</span>
        </button>

        <button
          onClick={() => handleTabChange('all')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs md:text-sm font-semibold transition ${
            activeTab === 'all'
              ? 'bg-white text-slate-900 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
          }`}
        >
          <Layers className="w-4 h-4 text-slate-700" />
          <span>All Views</span>
        </button>
      </div>

      {/* Tab 1: Autonomous Agent Console */}
      {(activeTab === 'agent' || activeTab === 'all') && (
        <div className="space-y-4">
          <AgentConsole />
        </div>
      )}

      {/* Tab 2: Amazon Location Corridors & Fuel Geofences */}
      {(activeTab === 'corridors' || activeTab === 'all') && (
        <div className="space-y-4">
          <CorridorMap />
        </div>
      )}

      {/* Tab 3: Financial Metrics, Anomaly Detection & Cash-Flow Recommendations */}
      {(activeTab === 'metrics' || activeTab === 'all') && (
        <div className="space-y-8">
          {/* AI Cash-Flow Assistant Card Section */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-emerald-950 text-white shadow-xl border border-slate-700">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                  <span>AI Cash-Flow Strategy</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500 text-slate-950 font-black uppercase tracking-wider">
                    Amazon Bedrock
                  </span>
                </h2>
                <p className="text-xs text-slate-400">AI-generated from your aggregate month-to-date figures. Estimates are indicative - verify before acting.</p>
              </div>
            </div>

            {aiState.error && (
              <p role="alert" className="mt-4 text-sm rounded-lg bg-rose-500/10 text-rose-200 border border-rose-500/30 px-3 py-2">{aiState.error}</p>
            )}
            {loadingInsights && <p className="mt-4 text-xs text-slate-400">Generating insights...</p>}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
              {(insights?.insights ?? []).map((insight, idx) => (
                <div
                  key={idx}
                  className="p-5 rounded-xl bg-slate-800/80 border border-slate-700/80 backdrop-blur flex flex-col justify-between hover:border-emerald-500/50 transition-colors"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-bold ${
                          insight.priority === 'HIGH'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {insight.priority} Priority
                      </span>
                      <Coins className="w-4 h-4 text-emerald-400" />
                    </div>
                    <h4 className="font-bold text-sm text-slate-100 mb-2">{insight.title}</h4>
                    <p className="text-xs text-slate-300 leading-relaxed">{insight.recommendation}</p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-700/80 flex items-center justify-between text-xs font-semibold">
                    <span className="text-slate-400">Est. Cash Benefit:</span>
                    <span className="text-emerald-400">{insight.estimatedSavingZar}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fuel Efficiency & Anomaly Detection (L/100km) */}
          <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Fuel Consumption & Anomaly Detection</h3>
                <p className="text-xs text-slate-500">Full-tank method: actual vs. target L/100km from consecutive full fill-ups</p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
                Threshold: &gt;15% Variance
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="px-6 py-3.5">Vehicle</th>
                    <th className="px-6 py-3.5">Distance</th>
                    <th className="px-6 py-3.5">Total Fuel</th>
                    <th className="px-6 py-3.5">Target (L/100km)</th>
                    <th className="px-6 py-3.5">Actual (L/100km)</th>
                    <th className="px-6 py-3.5">Variance</th>
                    <th className="px-6 py-3.5">Diagnosis</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {efficiency.map((e) => (
                    <tr key={e.vehicleId} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <span className="font-mono font-bold text-slate-900">{e.plateNumber}</span>
                        <div className="text-xs text-slate-500">{e.make} {e.model}</div>
                      </td>
                      <td className="px-6 py-4 font-medium text-slate-800">{formatKm(e.totalDistanceKm)}</td>
                      <td className="px-6 py-4 font-medium text-slate-800">{e.status === 'INSUFFICIENT_DATA' ? '-' : `${e.totalLitres.toFixed(1)} L`}</td>
                      <td className="px-6 py-4 text-xs font-semibold text-slate-600">{formatLPer100Km(e.targetEfficiencyLPer100Km)}</td>
                      <td className="px-6 py-4 font-bold text-slate-900">{e.actualEfficiencyLPer100Km === null ? 'Not enough data' : formatLPer100Km(e.actualEfficiencyLPer100Km)}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                            e.status === 'ANOMALY_DETECTED'
                              ? 'bg-rose-100 text-rose-800'
                              : e.variancePercent !== null && e.variancePercent <= 0
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {e.variancePercent === null ? 'n/a' : e.variancePercent > 0 ? `+${e.variancePercent}%` : `${e.variancePercent}%`}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs">
                        {e.status === 'ANOMALY_DETECTED' ? (
                          <span className="inline-flex items-center space-x-1 text-rose-700 font-semibold bg-rose-50 px-2 py-1 rounded border border-rose-200">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                            <span>{e.anomalyMessage}</span>
                          </span>
                        ) : (
                          <span className="text-slate-500">{e.anomalyMessage}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Operational Cost Per Kilometer Breakdown (R/km) */}
          <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Cost-per-Kilometer Breakdown (R/km)</h3>
                <p className="text-xs text-slate-500">True marginal operational cost: Fuel vs. Maintenance per vehicle</p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="px-6 py-3.5">Vehicle</th>
                    <th className="px-6 py-3.5">Distance</th>
                    <th className="px-6 py-3.5">Fuel Spend</th>
                    <th className="px-6 py-3.5">Maintenance Spend</th>
                    <th className="px-6 py-3.5">Fuel R/km</th>
                    <th className="px-6 py-3.5">Maint R/km</th>
                    <th className="px-6 py-3.5 text-right">Total R/km</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {costs.map((c) => (
                    <tr key={c.vehicleId} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <span className="font-mono font-bold text-slate-900">{c.plateNumber}</span>
                        <div className="text-xs text-slate-500">{c.make} {c.model}</div>
                      </td>
                      <td className="px-6 py-4 font-medium text-slate-800">{formatKm(c.totalDistanceKm)}</td>
                      <td className="px-6 py-4 font-semibold text-slate-900">{formatZAR(c.totalFuelCostZar)}</td>
                      <td className="px-6 py-4 font-semibold text-slate-900">{formatZAR(c.totalMaintenanceCostZar)}</td>
                      <td className="px-6 py-4 text-xs font-semibold text-amber-700">{formatRandPerKm(c.fuelCostPerKm)}</td>
                      <td className="px-6 py-4 text-xs font-semibold text-purple-700">{formatRandPerKm(c.maintenanceCostPerKm)}</td>
                      <td className="px-6 py-4 text-right font-extrabold text-emerald-700 text-base">
                        {formatRandPerKm(c.totalCostPerKm)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Fleet Utilisation */}
          <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6">
            <h3 className="text-base font-bold text-slate-900 mb-1">Fleet Asset Utilisation</h3>
            <p className="text-xs text-slate-500 mb-6">Percentage of active corridor dispatch vs. depot idle capacity</p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {utilisation.map((u) => (
                <div key={u.vehicleId} className="p-4 rounded-xl border border-slate-100 bg-slate-50/50 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-mono font-bold text-slate-900 text-sm">{u.plateNumber}</h4>
                      <p className="text-xs text-slate-500">{u.make} {u.model}</p>
                    </div>
                    <span className="text-xs font-bold text-slate-900">{u.utilisationRatePercent}%</span>
                  </div>

                  <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-2 rounded-full ${
                        u.utilisationRatePercent >= 70
                          ? 'bg-emerald-500'
                          : u.utilisationRatePercent >= 40
                          ? 'bg-blue-500'
                          : 'bg-amber-500'
                      }`}
                      style={{ width: `${u.utilisationRatePercent}%` }}
                    ></div>
                  </div>

                  <div className="flex justify-between text-xs text-slate-500 pt-1">
                    <span>Trips: {u.completedTripsCount} Done {u.activeTripsCount > 0 && `(${u.activeTripsCount} active)`}</span>
                    <span>{formatKm(u.totalDistanceKm)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
