// Supabase client — identity only. Session/JWT issuance lives here; every
// other piece of app data (trips, venues, itineraries) stays in our own
// Railway Postgres via lib/api.ts, never in Supabase.
//
// The anon key is safe to ship in the frontend by design (Supabase's own
// row-level-security model assumes it's public) — never put the service key
// here. Both come from EXPO_PUBLIC_* env vars, matching the existing
// EXPO_PUBLIC_GOOGLE_MAPS_KEY / EXPO_PUBLIC_API_URL convention.
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

/** False in any environment that hasn't configured Supabase — sign-in is
 * then simply unavailable, and the planner keeps working anonymously. */
export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

// createClient validates its URL eagerly, so a placeholder keeps import-time
// from throwing when auth isn't configured (local dev without a Supabase
// project yet, etc.) — every call this client would make simply never
// happens because isSupabaseConfigured gates it upstream.
export const supabase = createClient(
  SUPABASE_URL || 'https://placeholder.supabase.co',
  SUPABASE_ANON_KEY || 'placeholder-anon-key',
);
