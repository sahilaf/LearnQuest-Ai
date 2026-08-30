/**
 * Shared axios instance.
 *
 * OWNER: Member 3. SHARED FILE - change only by agreement (plan.md 2.4).
 *
 * Every API call in the app goes through this. Never call fetch() directly in a
 * component - add a function to the matching src/api/*.js module instead.
 */
import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

/**
 * Supplies the current Supabase access token.
 * AuthContext calls setTokenProvider() once on mount so this module never has to
 * import Supabase itself. supabase-js refreshes the token, so this stays live.
 */
let tokenProvider = async () => null;

export function setTokenProvider(fn) {
  tokenProvider = fn;
}

client.interceptors.request.use(async (config) => {
  try {
    const token = await tokenProvider();
    if (token) config.headers.Authorization = `Bearer ${token}`;
  } catch {
    // No token available - the backend decides whether that is allowed.
  }
  return config;
});

let onUnauthorized = () => {};

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

client.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const { response, config } = error;

    // One retry on 401 with a force-refreshed token (plan.md 8.2).
    if (response?.status === 401 && !config._retried) {
      config._retried = true;
      try {
        const token = await tokenProvider(true);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
          return client(config);
        }
      } catch {
        /* fall through to the handler below */
      }
      onUnauthorized();
    }

    // Normalise to the standard error shape (plan.md 4.2).
    return Promise.reject({
      status: response?.status ?? 0,
      detail: response?.data?.detail ?? error.message ?? 'Something went wrong.',
      code: response?.data?.code ?? 'NETWORK_ERROR',
    });
  }
);

export default client;
