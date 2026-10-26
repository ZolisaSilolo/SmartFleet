import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  subtext?: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: 'green' | 'blue' | 'amber' | 'red' | 'purple';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon: Icon,
  subtext,
  color = 'green',
}) => {
  const colorMap = {
    green: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    blue: 'bg-blue-50 text-blue-600 border-blue-100',
    amber: 'bg-amber-50 text-amber-600 border-amber-100',
    red: 'bg-rose-50 text-rose-600 border-rose-100',
    purple: 'bg-purple-50 text-purple-600 border-purple-100',
  };

  const iconBgMap = {
    green: 'bg-emerald-100 text-emerald-700',
    blue: 'bg-blue-100 text-blue-700',
    amber: 'bg-amber-100 text-amber-700',
    red: 'bg-rose-100 text-rose-700',
    purple: 'bg-purple-100 text-purple-700',
  };

  return (
    <div className={`p-5 rounded-xl border bg-white shadow-sm flex items-start justify-between transition-all hover:shadow-md ${colorMap[color]}`}>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">{title}</p>
        <h3 className="text-2xl font-bold text-slate-900 tracking-tight">{value}</h3>
        {subtext && <p className="text-xs font-medium text-slate-600 mt-1">{subtext}</p>}
      </div>
      <div className={`p-3 rounded-lg ${iconBgMap[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
    </div>
  );
};
