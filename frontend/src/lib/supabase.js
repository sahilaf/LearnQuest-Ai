/**
 * Supabase browser client.
 *
 * OWNER: Member 3. See plan.md §8.2.
 *
 * Only the anon key belongs here - it is public by design and safe to ship in the
 * bundle. The service_role key must NEVER appear in frontend code.
 *
 * Returns null when the env vars are missing, which puts AuthContext into dev mode
 * so the rest of the team can build without credentials.
 */
import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(url && anonKey);

export const supabase = isSupabaseConfigured
  ? createClient(url, anonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;
