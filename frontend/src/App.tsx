import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Vehicles } from './pages/Vehicles';
import { Drivers } from './pages/Drivers';
import { Trips } from './pages/Trips';
import { Fuel } from './pages/Fuel';
import { Maintenance } from './pages/Maintenance';
import { Stations } from './pages/Stations';
import { Analytics } from './pages/Analytics';
import { Login } from './pages/Login';

const Gate: React.FC = () => {
  const { status } = useAuth();
  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center" role="status" aria-label="Loading">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }
  if (status === 'signedOut') return <Login />;
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="vehicles" element={<Vehicles />} />
          <Route path="drivers" element={<Drivers />} />
          <Route path="trips" element={<Trips />} />
          <Route path="fuel" element={<Fuel />} />
          <Route path="maintenance" element={<Maintenance />} />
          <Route path="stations" element={<Stations />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export const App: React.FC = () => (
  <AuthProvider>
    <Gate />
  </AuthProvider>
);

export default App;
