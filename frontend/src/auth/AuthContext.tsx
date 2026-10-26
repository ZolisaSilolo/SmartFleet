import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getIdentity, Identity, signOut as cognitoSignOut } from '../services/auth';
import { SESSION_EXPIRED_EVENT } from '../services/http';

interface AuthState {
  status: 'loading' | 'signedOut' | 'signedIn';
  identity: Identity | null;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<AuthState['status']>('loading');
  const [identity, setIdentity] = useState<Identity | null>(null);

  const refresh = useCallback(async () => {
    const current = await getIdentity();
    setIdentity(current);
    setStatus(current ? 'signedIn' : 'signedOut');
  }, []);

  const signOut = useCallback(async () => {
    await cognitoSignOut();
    setIdentity(null);
    setStatus('signedOut');
  }, []);

  useEffect(() => {
    void refresh();
    const onExpired = () => {
      setIdentity(null);
      setStatus('signedOut');
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [refresh]);

  const value = useMemo(() => ({ status, identity, refresh, signOut }), [status, identity, refresh, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
