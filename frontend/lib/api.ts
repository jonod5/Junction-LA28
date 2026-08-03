import { supabase } from './supabase';

// On production web (Vercel), use relative URLs — vercel.json rewrites /api/* to Railway.
// On native or local dev, fall back to the explicit env var or localhost.
function getBaseUrl(): string {
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') return '';
  return 'http://localhost:8000';
}
const BASE_URL = getBaseUrl();

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(options?.headers as Record<string, string> | undefined) };
  // Attaches the current Supabase session's access token when one exists —
  // every endpoint that doesn't call get_current_user just ignores it, so
  // this is safe to send unconditionally rather than threading an
  // "is this an authed call" flag through every api.* function.
  const { data } = await supabase.auth.getSession();
  if (data.session?.access_token) headers['Authorization'] = `Bearer ${data.session.access_token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;
  const body = await res.json();
  if (!res.ok) throw new Error(body?.detail ?? `HTTP ${res.status}`);
  return body as T;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Stop {
  id: number;
  trip_id: number;
  venue_id: number | null;
  name: string;
  lat: number;
  lng: number;
  order_index: number;
}

export interface Leg {
  id: number;
  trip_id: number;
  from_stop_id: number;
  to_stop_id: number;
  mode: string;
  distance_m: number | null;
  duration_s: number | null;
  polyline: string | null;
}

export interface Trip {
  id: number;
  name: string;
  created_at: string;
  stops: Stop[];
  legs: Leg[];
}

export interface DirectionStep {
  mode: string;
  instruction: string;
  maneuver?: string;
  distance_m: number;
  duration_s: number;
  polyline?: string;
  transit_line?: string;
  transit_line_short?: string;
  transit_vehicle?: string;
  transit_color?: string;
  departure_stop?: string;
  arrival_stop?: string;
  num_stops?: number;
  headsign?: string;
  sub_steps?: string[];
}

export interface DirectionsResult {
  mode: string;
  distance_m: number;
  duration_s: number;
  polyline: string;
  steps: DirectionStep[];
}

export interface ParkingOption {
  id: number;
  lot_name: string | null;
  is_official: boolean | null;
  price_min: number | null;
  price_max: number | null;
  price_notes: string | null;
  pricing_basis: string | null;
  has_surge_pricing: boolean | null;
  surge_notes: string | null;
  is_closest_to_entrance: boolean | null;
  notes: string | null;
}

export interface TransitAccess {
  id: number;
  line: string | null;
  mode: string | null;
  stop_name: string | null;
  walk_time_min: number | null;
  nearest_metro_station: string | null;
  bus_lines_serving: string | null;
  bike_lane_nearby: boolean | null;
  gbfs_dock_description: string | null;
  transit_notes: string | null;
}

export interface CurbDropoff {
  id: number;
  rideshare_zone_description: string | null;
  rideshare_zone_open_window: string | null;
  taxi_accessible_zone: string | null;
  private_vehicle_dropoff: string | null;
  no_stop_zones: string | null;
  curbside_restrictions: string | null;
}

export interface CongestionTdm {
  id: number;
  recommended_arrival_hrs_before_min: number | null;
  recommended_arrival_hrs_before_max: number | null;
  arrival_notes: string | null;
  high_congestion_entry_roads: string | null;
  known_congestion_exit_roads: string | null;
  general_tdm_notes: string | null;
}

export interface VenueDetail {
  id: number;
  name: string;
  sport_use: string | null;
  zone: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  total_spaces: number | null;
  total_lots: number | null;
  capacity_text: string | null;
  games_time_access_notes: string | null;
  games_time_parking_policy: string;
  parking_options: ParkingOption[];
  transit_accesses: TransitAccess[];
  curb_dropoffs: CurbDropoff[];
  congestion_tdm: CongestionTdm | null;
}

// ── Micromobility (live GBFS + static Metro Micro) ─────────────────────────────

export interface MicromobilityItem {
  provider: string;
  kind: 'vehicle' | 'station';
  vehicle_type: 'bike' | 'ebike' | 'scooter';
  lat: number;
  lng: number;
  id: string | null;
  distance_m: number;
  // Present on stations only:
  name?: string;
  num_bikes_available?: number | null;
  num_ebikes_available?: number | null;
  num_docks_available?: number | null;
}

export interface MetroMicroZoneRef {
  id: string;
  name: string;
}

export interface MetroMicroService {
  available: boolean;
  zones: MetroMicroZoneRef[];
  base_fare_usd: number;
  reduced_fare_usd: number;
  transfer_fare_usd: number;
  transfer_window_min: number;
  max_wait_min: number;
  booking_url: string;
  fare_is_estimate: boolean;
  attribution: string;
}

export interface MicromobilityResult {
  query: { lat: number; lng: number; radius_m: number };
  count: number;
  items: MicromobilityItem[];
  pricing: Record<string, unknown[]>;
  metro_micro: MetroMicroService;
  metadata: {
    attribution: string;
    license: string;
    cache_ttl_max_s: number;
    errors: Record<string, string[]>;
  };
}

// ── Live transit (Swiftly GTFS-RT) ─────────────────────────────────────────────

export interface TransitLiveStatus {
  configured: boolean;
  status: 'live' | 'no_service' | 'scheduled';
  live: boolean | null;
  vehicles_running: number;
  line: string | null;
  targets: string[];
}

// ── Route optimization engine ──────────────────────────────────────────────────

export type RouteMode =
  | 'walk' | 'bike' | 'scooter' | 'transit' | 'metro_micro' | 'ridehail';

export interface RouteLeg {
  mode: string;
  distance_m: number | null;
  duration_s: number | null;
  polyline: string;
  steps: DirectionStep[];
}

export interface RouteOption {
  id: string;
  label: string;
  modes: RouteMode[];
  total_minutes: number;
  total_cost_usd: number;
  cost_is_estimate: boolean;
  num_transfers: number;
  legs: RouteLeg[];
  score: number;
  score_breakdown: {
    time_norm: number;
    cost_norm: number;
    num_transfers: number;
    weights: { time: number; cost: number; transfer: number };
  };
}

export interface RouteOptimizeResult {
  origin: { lat: number; lng: number };
  destination: { lat: number; lng: number };
  departure_time: number | null;
  preferences: string[] | null;
  weights: { time: number; cost: number; transfer: number };
  count: number;
  options: RouteOption[];
  notes: string[];
}

export interface RouteOptimizeRequest {
  origin: { lat: number; lng: number };
  destination: { lat: number; lng: number };
  preferences?: RouteMode[] | null;
  departure_time?: number | null;
}

// ── Saved itineraries ────────────────────────────────────────────────────────

/** Shape of Itinerary.saved_plan — owned by this file, stored verbatim by the
 *  backend. Legs are keyed by "<fromIndex>-<toIndex>" (stop order position),
 *  not stop ids — ids are re-assigned every time a trip is rehydrated, but
 *  position is stable. */
export interface SavedStopSnapshot {
  venue_id: number | null;
  name: string;
  lat: number;
  lng: number;
}

export interface SavedLegSnapshot {
  selected_option: RouteOption;
}

export interface SavedPlanSnapshot {
  stops: SavedStopSnapshot[];
  preferences: RouteMode[] | null;
  legs: Record<string, SavedLegSnapshot>;
}

export interface Itinerary {
  id: number;
  name: string;
  trip_date: string | null;
  is_pinned: boolean;
  saved_plan: SavedPlanSnapshot;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface ItineraryListResult {
  items: Itinerary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ItineraryListParams {
  status?: 'upcoming' | 'past' | 'all';
  tag?: string;
  sort?: 'trip_date' | 'created_at' | 'updated_at';
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface ItineraryCreateBody {
  name: string;
  trip_date?: string | null;
  is_pinned?: boolean;
  tags?: string[];
  saved_plan: SavedPlanSnapshot;
}

export interface ItineraryUpdateBody {
  name?: string;
  trip_date?: string | null;
  is_pinned?: boolean;
  tags?: string[];
}

// ── API ───────────────────────────────────────────────────────────────────────

export const api = {
  createTrip: (name: string) =>
    request<Trip>('/api/trips', { method: 'POST', body: JSON.stringify({ name }) }),

  getTrip: (id: number) => request<Trip>(`/api/trips/${id}`),

  deleteTrip: (id: number) => request<void>(`/api/trips/${id}`, { method: 'DELETE' }),

  addStop: (tripId: number, body: { venue_id?: number; name: string; lat: number; lng: number }) =>
    request<Stop>(`/api/trips/${tripId}/stops`, { method: 'POST', body: JSON.stringify(body) }),

  removeStop: (tripId: number, stopId: number) =>
    request<void>(`/api/trips/${tripId}/stops/${stopId}`, { method: 'DELETE' }),

  reorderStops: (tripId: number, order: { stop_id: number; order_index: number }[]) =>
    request<Trip>(`/api/trips/${tripId}/stops/reorder`, {
      method: 'PATCH',
      body: JSON.stringify(order),
    }),

  getDirections: (origin: string, destination: string, mode: string) =>
    request<DirectionsResult>(
      `/api/directions?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&mode=${mode}`,
    ),

  upsertLeg: (
    tripId: number,
    body: {
      from_stop_id: number;
      to_stop_id: number;
      mode: string;
      distance_m: number;
      duration_s: number;
      polyline: string;
    },
  ) => request<Leg>(`/api/trips/${tripId}/legs`, { method: 'PUT', body: JSON.stringify(body) }),

  getVenue: (id: number) => request<VenueDetail>(`/api/venues/${id}`),

  getMicromobility: (lat: number, lng: number, radiusM = 800) =>
    request<MicromobilityResult>(
      `/api/micromobility?lat=${lat}&lng=${lng}&radius_m=${radiusM}`,
    ),

  optimizeRoutes: (body: RouteOptimizeRequest) =>
    request<RouteOptimizeResult>('/api/routes/optimize', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getTransitLive: (line: string) =>
    request<TransitLiveStatus>(`/api/transit/live?line=${encodeURIComponent(line)}`),

  listItineraries: (params: ItineraryListParams = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) q.set(k, String(v));
    });
    const qs = q.toString();
    return request<ItineraryListResult>(`/api/itineraries${qs ? `?${qs}` : ''}`);
  },

  getItinerary: (id: number) => request<Itinerary>(`/api/itineraries/${id}`),

  createItinerary: (body: ItineraryCreateBody) =>
    request<Itinerary>('/api/itineraries', { method: 'POST', body: JSON.stringify(body) }),

  updateItinerary: (id: number, body: ItineraryUpdateBody) =>
    request<Itinerary>(`/api/itineraries/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteItinerary: (id: number) => request<void>(`/api/itineraries/${id}`, { method: 'DELETE' }),
};
