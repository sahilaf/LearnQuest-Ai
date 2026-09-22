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
  email: 'admin@learnquest.ai',
  full_name: 'Alex Mercer (Admin)',
  role: 'admin',
  avatar_url: null,
};

function generateDevUserId(email) {
  if (email === 'admin@learnquest.ai') {
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
  const cleanEmail = (email || '').trim().toLowerCase();
  const isExplicitAdmin = cleanEmail === 'admin@learnquest.ai';
  return {
    id,
    email: cleanEmail,
    full_name: meta.full_name ?? meta.name ?? cleanEmail,
    avatar_url: meta.avatar_url ?? meta.picture ?? null,
    role: isExplicitAdmin ? 'admin' : 'student',
  };
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
        const cleanEmail = (userData.email || baseUser.email || '').trim().toLowerCase();
        const isExplicitAdmin = cleanEmail === 'admin@learnquest.ai';
        setUser((prev) => ({
          ...(prev || baseUser),
          ...userData,
          role: isExplicitAdmin ? 'admin' : 'student',
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
    // --- URL inspection: what, if anything, did the provider send back? ---
    const urlHash = typeof window !== 'undefined' ? window.location.hash : '';
    const urlSearch = typeof window !== 'undefined' ? window.location.search : '';

    const hashParams = new URLSearchParams(urlHash.replace(/^#/, ''));
    const searchParams = new URLSearchParams(urlSearch);

    const oauthError = hashParams.get('error') || searchParams.get('error');
    const oauthErrorDesc =
      hashParams.get('error_description') || searchParams.get('error_description');
    const oauthCode = searchParams.get('code');

    if (oauthError) {
      let msg = oauthErrorDesc
        ? decodeURIComponent(oauthErrorDesc.replace(/\+/g, ' '))
        : oauthError;
      if (
        oauthError === 'unsupported_provider'
        || msg.toLowerCase().includes('provider is not enabled')
      ) {
        msg =
          'Google sign-in is not enabled on this Supabase project yet. Please sign in '
          + 'with email/password, or enable the Google provider under Supabase Dashboard '
          + '-> Authentication -> Providers.';
      } else if (msg.toLowerCase().includes('unable to exchange external code')) {
        msg =
          'Google OAuth configuration error: Supabase could not exchange the code with '
          + 'Google. Verify the Google Client ID and Secret in Supabase match Google Cloud '
          + 'Console, and that the redirect URI there is '
          + 'https://dkyvtuzutcblcpeerqeo.supabase.co/auth/v1/callback';
      }
      setError(msg);
      // Clear the error off the URL so it does not survive navigation.
      if (typeof window !== 'undefined' && window.history?.replaceState) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }

    // Credentials genuinely on their way back from the provider.
    const hasAuthCredentialsInUrl = urlHash.includes('access_token=') || Boolean(oauthCode);

    // Only hold `loading` while a session is actually inbound. Treating an
    // error redirect as "still waiting" left the app spinning for the whole
    // timeout before reporting a failure it already knew about.
    const hasAuthRedirectInUrl = hasAuthCredentialsInUrl && !oauthError;

    // PKCE returns a code that must be exchanged for a session. (The current
    // client uses the implicit flow, so this is a no-op there - it keeps
    // working if the flow type is ever switched.)
    if (oauthCode && !oauthError) {
      supabase.auth
        .exchangeCodeForSession(oauthCode)
        .then(({ data, error: exchangeErr }) => {
          if (!isMounted) return;
          if (exchangeErr) {
            setError(exchangeErr.message);
            setLoading(false);
          } else if (data?.session) {
            const appUser = toAppUser(data.session);
            setUser(appUser);
            setLoading(false);
            if (appUser) syncWithBackend(appUser);
          }
          if (typeof window !== 'undefined' && window.history?.replaceState) {
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        })
        .catch((err) => {
          if (!isMounted) return;
          console.warn('OAuth code exchange failed:', err);
          setLoading(false);
        });
    }

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

      if (!appUser && event === 'INITIAL_SESSION' && hasAuthRedirectInUrl) {
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
      clearError: () => setError(null),
      isAuthenticated: Boolean(user),
      isAdmin: user?.email === 'admin@learnquest.ai' && user?.role === 'admin',
      devMode: !isSupabaseConfigured,

      async login(email, password) {
        setError(null);
        if (!isSupabaseConfigured) {
          const devId = generateDevUserId(email);
          const devAccount = {
            id: devId,
            email,
            full_name: email.split('@')[0].replace('.', ' '),
            role: email === 'admin@learnquest.ai' ? 'admin' : 'student',
            avatar_url: null,
          };
          localStorage.setItem('learnquest_dev_user', JSON.stringify(devAccount));
          setTokenProvider(async () => `dev:${devAccount.id}:${devAccount.email}`);
          setUser(devAccount);
          await syncWithBackend(devAccount);
          return null;
        }
        const cleanEmail = (email || '').trim().toLowerCase();
        const { data, error: err } = await supabase.auth.signInWithPassword({ email: cleanEmail, password });
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
          const devAccount = {
            id: '00000000-0000-4000-8000-000000000099',
            email: 'google.user@learnquest.local',
            full_name: 'Google User',
            role: 'student',
            avatar_url: null,
          };
          localStorage.setItem('learnquest_dev_user', JSON.stringify(devAccount));
          setTokenProvider(async () => `dev:${devAccount.id}:${devAccount.email}`);
          setUser(devAccount);
          return null;
        }
        const { error: err } = await supabase.auth.signInWithOAuth({
          provider: 'google',
          options: {
            redirectTo: `${window.location.origin}/dashboard`,
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
