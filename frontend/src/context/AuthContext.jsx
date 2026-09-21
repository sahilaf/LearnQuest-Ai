/**
 * Authentication context - Supabase Auth.
 *
 * OWNER: Member 3. See plan.md §8.2.
 *
 * Handles Supabase session, token refresh, and synchronization with backend public.users.
 * When Supabase keys are not configured, runs in DEV MODE and provides a developer user.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { setTokenProvider, setUnauthorizedHandler } from '../api/client';
import { syncUser } from '../api/users';
import { supabase, isSupabaseConfigured } from '../lib/supabase';

const AuthContext = createContext(null);

const DEV_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'dev@learnquest.local',
  full_name: 'Dev User',
  role: 'admin',
  avatar_url: null,
};

function generateDevUserId(email) {
  if (email === 'dev@learnquest.local' || email === 'admin@learnquest.ai') {
    return '00000000-0000-0000-0000-000000000001';
  }
  let hash = 0;
  for (let i = 0; i < email.length; i++) {
    hash = ((hash << 5) - hash) + email.charCodeAt(i);
    hash |= 0;
  }
  const hex = Math.abs(hash).toString(16).padStart(8, '0');
  return `00000000-0000-4000-8000-${hex.padEnd(12, '0').slice(0, 12)}`;
}

function toAppUser(session) {
  if (!session?.user) return null;
  const { id, email, user_metadata: meta = {} } = session.user;
  return {
    id,
    email,
    full_name: meta.full_name ?? meta.name ?? email,
    avatar_url: meta.avatar_url ?? meta.picture ?? null,
    role: meta.role ?? 'student',
  };
}


// --- TEMPORARY OAuth diagnostic (remove once sign-in is confirmed working) ---
// The redirect wipes the console, so the timeline is written to localStorage.
// After a failed sign-in run:  JSON.parse(localStorage.getItem('lq_auth_trace'))
function authTrace(step, detail) {
  try {
    const trace = JSON.parse(localStorage.getItem('lq_auth_trace') || '[]');
    trace.push({ t: new Date().toISOString().slice(11, 23), step, ...detail });
    localStorage.setItem('lq_auth_trace', JSON.stringify(trace.slice(-40)));
  } catch {
    /* storage unavailable - diagnostics are best effort */
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Sync user with backend database to get real role and ensure public.users exists
  const syncWithBackend = async (baseUser) => {
    try {
      const res = await syncUser();
      const userData = res?.user || res?.data?.user;
      if (userData) {
        setUser((prev) => ({
          ...(prev || baseUser),
          ...userData,
        }));
      }
    } catch (err) {
      console.warn('Backend user sync failed, falling back to session user:', err);
    }
  };

  useEffect(() => {
    if (!isSupabaseConfigured) {
      const stored = localStorage.getItem('learnquest_dev_user');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setTokenProvider(async () => `dev:${parsed.id}:${parsed.email}`);
          setUser(parsed);
        } catch {
          setTokenProvider(async () => null);
          setUser(null);
        }
      } else {
        setTokenProvider(async () => null);
        setUser(null);
      }
      setLoading(false);
      return undefined;
    }

    let isMounted = true;
    authTrace('mount', {
      path: window.location.pathname,
      hash: window.location.hash.slice(0, 60),
      search: window.location.search.slice(0, 60),
    });

    // Credentials actually coming back from the provider.
    const hasAuthCredentialsInUrl =
      typeof window !== 'undefined' &&
      (window.location.hash.includes('access_token=') ||
        window.location.search.includes('code='));

    // The provider already told us it failed - nothing is in flight.
    const hasAuthErrorInUrl =
      typeof window !== 'undefined' &&
      (window.location.hash.includes('error=') ||
        window.location.search.includes('error='));

    // Only hold `loading` while a session is genuinely on its way. Treating an
    // error redirect as "still waiting" left the app spinning for the full
    // timeout before showing a failure it already knew about.
    const hasAuthRedirectInUrl = hasAuthCredentialsInUrl && !hasAuthErrorInUrl;

    // The interceptor in api/client.js pulls the token from here on every request.
    setTokenProvider(async (forceRefresh = false) => {
      if (forceRefresh) {
        try {
          const { data, error } = await supabase.auth.refreshSession();
          if (error || !data?.session) return null;
          return data.session.access_token;
        } catch {
          return null;
        }
      }
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token ?? null;
    });

    // Supabase reports a failed OAuth round trip by putting error= on the URL
    // it sends you back to. Without this the user is silently returned to the
    // login page with no idea what went wrong.
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(
        window.location.search || window.location.hash.replace(/^#/, '')
      );
      const oauthError = params.get('error_description') || params.get('error');
      if (oauthError) {
        console.error('OAuth sign-in failed:', oauthError);
        setError(decodeURIComponent(oauthError.replace(/\+/g, ' ')));
      }
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (!isMounted) return;
      const appUser = toAppUser(session);

      // supabase-js fires INITIAL_SESSION as soon as we subscribe. Coming back
      // from Google the credentials are still sitting unparsed in the URL, so
      // that first event carries a null session. Treating it as "signed out"
      // cleared `loading`, PrivateRoute redirected to /login, and the redirect
      // threw away the tokens in the URL - which is exactly "I signed in with
      // Google and landed back on the login page". Wait for the real event.
      authTrace('event', { event, session: appUser ? 'YES' : 'null', hasAuthRedirectInUrl });

      if (!appUser && event === 'INITIAL_SESSION' && hasAuthRedirectInUrl) {
        authTrace('event-ignored', { why: 'INITIAL_SESSION null during OAuth return' });
        return;
      }

      setUser(appUser);
      setLoading(false);
      if (appUser) {
        await syncWithBackend(appUser);
      }
    });

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!isMounted) return;
        const appUser = toAppUser(data.session);
        authTrace('getSession', { session: appUser ? 'YES' : 'null', hasAuthRedirectInUrl });
        if (appUser) {
          setUser(appUser);
          setLoading(false);
          syncWithBackend(appUser);
        } else if (!hasAuthRedirectInUrl) {
          setUser(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        // A stored session whose token has expired makes getSession() call
        // Supabase to refresh it. If the project is paused, deleted or simply
        // offline that request rejects - and without this catch nothing ever
        // cleared `loading`, so the whole app sat on a spinner forever.
        // Failing to restore a session means "signed out", not "wait".
        if (!isMounted) return;
        authTrace('getSession-rejected', { err: String(err?.message || err).slice(0, 80) });
        console.warn('Could not restore session; continuing signed out.', err);

        // ...unless we are mid-OAuth. On the way back from Google the URL
        // carries `?code=`, and supabase-js still has to exchange it over the
        // network before any session exists. Clearing the user here declares
        // "signed out" while that is still in flight, and PrivateRoute then
        // redirects to /login - which discards the code and loses the login.
        // onAuthStateChange is what resolves this case; let it.
        if (hasAuthRedirectInUrl) return;

        setUser(null);
        setLoading(false);
      });

    // Safety net so a hung auth call cannot spin forever. The OAuth window is
    // much longer than the plain one: a PKCE code exchange is a full network
    // round trip to Supabase, and 4s was short enough to fire mid-exchange on
    // a slow connection - bouncing the user to /login just as they signed in.
    const timeoutId = setTimeout(() => {
      if (!isMounted) return;
      authTrace('timeout-fired', { note: 'gave up waiting for a session' });
      setLoading(false);
    }, hasAuthRedirectInUrl ? 20000 : 6000);

    return () => {
      isMounted = false;
      if (timeoutId) clearTimeout(timeoutId);
      subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(async () => {
      if (isSupabaseConfigured) {
        try {
          await supabase.auth.signOut();
        } catch {
          // ignore sign out errors
        }
      }
      setUser(null);
    });
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
        if (!isSupabaseConfigured) {
          const devId = generateDevUserId(email);
          const devAccount = {
            id: devId,
            email,
            full_name: email.split('@')[0].replace('.', ' '),
            role: email.includes('admin') ? 'admin' : 'student',
            avatar_url: null,
          };
          localStorage.setItem('learnquest_dev_user', JSON.stringify(devAccount));
          setTokenProvider(async () => `dev:${devAccount.id}:${devAccount.email}`);
          setUser(devAccount);
          await syncWithBackend(devAccount);
          return null;
        }
        const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
        if (err) {
          setError(err.message);
          return err;
        }
        const appUser = toAppUser(data.session);
        setUser(appUser);
        if (appUser) await syncWithBackend(appUser);
        return null;
      },

      async loginWithGoogle() {
        setError(null);
        if (!isSupabaseConfigured) {
          const devAccount = { ...DEV_USER };
          localStorage.setItem('learnquest_dev_user', JSON.stringify(devAccount));
          setTokenProvider(async () => `dev:${devAccount.id}:${devAccount.email}`);
          setUser(devAccount);
          return null;
        }
        const { error: err } = await supabase.auth.signInWithOAuth({
          provider: 'google',
          options: {
            redirectTo: `${window.location.origin}/dashboard`,
            queryParams: {
              access_type: 'offline',
              prompt: 'select_account',
            },
          },
        });
        if (err) {
          setError(err.message);
          return err;
        }
        return null;
      },

      async register(email, password, fullName) {
        setError(null);
        if (!isSupabaseConfigured) {
          const devId = generateDevUserId(email);
          const devAccount = {
            id: devId,
            email,
            full_name: fullName || email.split('@')[0],
            role: 'student',
            avatar_url: null,
          };
          localStorage.setItem('learnquest_dev_user', JSON.stringify(devAccount));
          setTokenProvider(async () => `dev:${devAccount.id}:${devAccount.email}`);
          setUser(devAccount);
          await syncWithBackend(devAccount);
          return null;
        }
        const { data, error: err } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } },
        });
        if (err) {
          setError(err.message);
          return err;
        }
        if (data?.session) {
          const appUser = toAppUser(data.session);
          setUser(appUser);
          if (appUser) await syncWithBackend(appUser);
        } else if (data?.user) {
          const { data: signData } = await supabase.auth.signInWithPassword({ email, password });
          if (signData?.session) {
            const appUser = toAppUser(signData.session);
            setUser(appUser);
            if (appUser) await syncWithBackend(appUser);
          }
        }
        return null;
      },

      async resetPassword(email) {
        setError(null);
        if (!isSupabaseConfigured) {
          return null;
        }
        const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/login`,
        });
        if (err) {
          setError(err.message);
          return err;
        }
        return null;
      },

      async logout() {
        if (isSupabaseConfigured) await supabase.auth.signOut();
        localStorage.removeItem('learnquest_dev_user');
        setTokenProvider(async () => null);
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
