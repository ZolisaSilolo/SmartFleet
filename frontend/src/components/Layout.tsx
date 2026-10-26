import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Truck,
  Users,
  Navigation,
  Fuel,
  Wrench,
  Sparkles,
  MapPin,
  LogOut,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

export const Layout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { identity, signOut } = useAuth();

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Vehicles', path: '/vehicles', icon: Truck },
    { name: 'Drivers', path: '/drivers', icon: Users },
    { name: 'Trips', path: '/trips', icon: Navigation },
    { name: 'Fuel', path: '/fuel', icon: Fuel },
    { name: 'Maintenance', path: '/maintenance', icon: Wrench },
    { name: 'Stations', path: '/stations', icon: MapPin },
    { name: 'Analytics & AI', path: '/analytics', icon: Sparkles },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      {/* Mobile Top Header */}
      <header className="md:hidden bg-slate-900 text-white px-4 py-3 flex items-center justify-between sticky top-0 z-40 shadow-md">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center font-bold text-slate-900">
            SF
          </div>
          <div>
            <span className="font-bold tracking-tight text-white">SmartFleet</span>
            <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-semibold">ZA 🇿🇦</span>
          </div>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </header>

      {/* Sidebar Navigation */}
      <aside
        className={`${
          mobileMenuOpen ? 'block' : 'hidden'
        } md:block w-full md:w-64 bg-slate-900 text-slate-300 flex-shrink-0 flex flex-col z-30 transition-all`}
      >
        <div className="p-6 border-b border-slate-800 hidden md:flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center font-black text-slate-950 text-xl shadow-lg shadow-emerald-500/20">
              SF
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-white text-lg tracking-tight">SmartFleet</span>
                <span className="text-sm">🇿🇦</span>
              </div>
              <p className="text-xs text-slate-400">SME Cash-Flow Assistant</p>
            </div>
          </div>
        </div>

        {/* Tenant Indicator */}
        <div className="px-6 py-3.5 bg-slate-950/60 border-b border-slate-800/80 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-400">Tenant:</span>
          </div>
          <span className="font-mono text-emerald-400 font-semibold bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
            {identity?.tenantId}
          </span>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all ${
                    isActive
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30 font-semibold'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Account */}
        <div className="p-4 border-t border-slate-800 space-y-2 bg-slate-950/40">
          <p className="text-xs text-slate-400 truncate" title={identity?.email}>{identity?.email}</p>
          <button
            onClick={() => void signOut()}
            className="w-full flex items-center justify-center space-x-2 px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors border border-slate-700/80"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign out</span>
          </button>
        </div>      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
