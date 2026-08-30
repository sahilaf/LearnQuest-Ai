/**
 * Authentication context.
 *
 * OWNER: Member 3. See plan.md 8.2.
 *
 * Until Firebase env vars are filled in, this runs in DEV MODE: it hands back a
 * fake signed-in user so Members 1, 2 and 4 can build pages on day 1. The backend
 * mirrors this with DEV_ALLOW_ANONYMOUS.
 *
 * TODO(M3): replace the dev branch with real Firebase auth in week 1 day 2.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { setTokenProvider, setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

const FIREBASE_CONFIGURED = Boolean(import.meta.env.VITE_FIREBASE_API_KEY);

const DEV_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'dev@learnquest.local',
  full_name: 'Dev User',
  role: 'admin',
  avatar_url: null,
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!FIREBASE_CONFIGURED) {
      // Dev mode: no Firebase keys yet.
      setTokenProvider(async () => null);
      setUser(DEV_USER);
      setLoading(false);
      return;
    }

    // TODO(M3): initialise Firebase, subscribe to onAuthStateChanged, and
    // register the real token provider:
    //   setTokenProvider((force) => auth.currentUser?.getIdToken(force) ?? null);
    // Then POST /api/auth/sync and store the returned profile.
    setLoading(false);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === 'admin',
      devMode: !FIREBASE_CONFIGURED,

      // TODO(M3): implement all four against Firebase.
      async login() {
        setError('Firebase is not configured yet. See plan.md 8.2.');
      },
      async register() {
        setError('Firebase is not configured yet. See plan.md 8.2.');
      },
      async resetPassword() {
        setError('Firebase is not configured yet. See plan.md 8.2.');
      },
      async logout() {
        setUser(null);
      },
    }),
    [user, loading, error]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
