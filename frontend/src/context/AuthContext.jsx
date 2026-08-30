/**
 * Authentication context - Supabase Auth.
 *
 * OWNER: Member 3. See plan.md §8.2.
 *
 * When VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are missing this runs in DEV MODE
 * and hands back a fake signed-in user, so Members 1, 2 and 4 can build pages before
 * credentials exist. The backend mirrors this with DEV_ALLOW_ANONYMOUS.
 *
 * TODO(M3): after sign-in, call POST /api/auth/sync so the public.users row exists,
 * and use the role it returns instead of the hardcoded 'student' below.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { setTokenProvider, setUnauthorizedHandler } from '../api/client';
import { supabase, isSupabaseConfigured } from '../lib/supabase';

const AuthContext = createContext(null);

const DEV_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'dev@learnquest.local',
  full_name: 'Dev User',
  role: 'admin',
  avatar_url: null,
};

function toAppUser(session) {
  if (!session?.user) return null;
  const { id, email, user_metadata: meta = {} } = session.user;
  return {
    id,
    email,
    full_name: meta.full_name ?? meta.name ?? email,
    avatar_url: meta.avatar_url ?? null,
    // TODO(M3): real role comes from public.users via /api/auth/sync.
    role: 'student',
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isSupabaseConfigured) {
      setTokenProvider(async () => null);
      setUser(DEV_USER);
      setLoading(false);
      return undefined;
    }

    // The interceptor in api/client.js pulls the token from here on every request.
    // supabase-js refreshes it automatically, so this always returns a live token.
    setTokenProvider(async () => {
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token ?? null;
    });

    supabase.auth.getSession().then(({ data }) => {
      setUser(toAppUser(data.session));
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(toAppUser(session));
    });

    return () => subscription.unsubscribe();
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
      devMode: !isSupabaseConfigured,

      async login(email, password) {
        setError(null);
        if (!isSupabaseConfigured) return setError('Supabase is not configured yet.');
        const { error: err } = await supabase.auth.signInWithPassword({ email, password });
        if (err) setError(err.message);
        return err ?? null;
      },

      async loginWithGoogle() {
        setError(null);
        if (!isSupabaseConfigured) return setError('Supabase is not configured yet.');
        const { error: err } = await supabase.auth.signInWithOAuth({
          provider: 'google',
          options: { redirectTo: `${window.location.origin}/dashboard` },
        });
        if (err) setError(err.message);
        return err ?? null;
      },

      async register(email, password, fullName) {
        setError(null);
        if (!isSupabaseConfigured) return setError('Supabase is not configured yet.');
        const { error: err } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } },
        });
        if (err) setError(err.message);
        return err ?? null;
      },

      async resetPassword(email) {
        setError(null);
        if (!isSupabaseConfigured) return setError('Supabase is not configured yet.');
        const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/login`,
        });
        if (err) setError(err.message);
        return err ?? null;
      },

      async logout() {
        if (isSupabaseConfigured) await supabase.auth.signOut();
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
