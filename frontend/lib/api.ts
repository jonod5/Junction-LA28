// On production web (Vercel), use relative URLs — vercel.json rewrites /api/* to Railway.
// On native or local dev, fall back to the explicit env var or localhost.
function getBaseUrl(): string {
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') return '';
  return 'http://localhost:8000';
}
const BASE_URL = getBaseUrl();

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail ?? `HTTP ${res.status}`);
  return data as T;
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
  taxi_accessible_zone: boolean | null;
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
};
