// Hand-verified transit + mobility data for all 6 LA28 venues.
// Source: Venue_Data_Collection.pdf (UCLA SURP 2026, July 2026, field-verified).

import { brand } from '@/constants/theme';

export type TransitLayer = 'rail' | 'bus' | 'bike' | 'scooter' | 'dropoff';

export interface VenueTransitPoint {
  id: string;
  type: TransitLayer;
  name: string;
  lat: number;
  lng: number;
  venueIds: number[];
  lines?: string[];
  walkMin?: number;
  providers?: string[];
  note?: string;
}

export const TRANSIT_LAYER_CONFIG: Record<
  TransitLayer,
  { label: string; fill: string; displayName: string }
> = {
  rail:    { label: 'M', fill: '#1B4FD8', displayName: 'Metro Rail' },
  bus:     { label: 'B', fill: brand.poppy, displayName: 'Bus Stop' },   // orange
  bike:    { label: 'W', fill: '#DC2626', displayName: 'Bike Share' },   // Metro Bike -> red
  scooter: { label: 'E', fill: '#00D66D', displayName: 'Scooter Zone' }, // Bird green (approx. — Bird's brand green isn't in a public brand-kit hex, adjust if you have the exact value)
  dropoff: { label: 'P', fill: '#FF00BF', displayName: 'Rideshare P/U' }, // Lyft magenta/pink
};

export const VENUE_TRANSIT: VenueTransitPoint[] = [
  // ── Metro Rail Stations ──────────────────────────────────────────────────────

  {
    id: 'rail-expo-usc',
    type: 'rail',
    name: 'Expo Park/USC Station',
    lat: 34.0190,
    lng: -118.2856,
    venueIds: [1],
    lines: ['E Line (Expo)'],
    walkMin: 6,
  },
  {
    id: 'rail-inglewood',
    type: 'rail',
    name: 'Downtown Inglewood Station',
    lat: 33.9613,
    lng: -118.3424,
    venueIds: [2],
    lines: ['K Line (Crenshaw)'],
    walkMin: 23,
  },
  {
    id: 'rail-chinatown',
    type: 'rail',
    name: 'Chinatown Station',
    lat: 34.0634,
    lng: -118.2376,
    venueIds: [3],
    lines: ['A Line (Blue)'],
    walkMin: 27,
    note: 'Or board free Dodger Stadium Express from Union Station',
  },
  {
    id: 'rail-union-station',
    type: 'rail',
    name: 'Union Station',
    lat: 34.0562,
    lng: -118.2365,
    venueIds: [3],
    lines: ['A Line', 'B Line', 'J Line', 'Metrolink'],
    note: 'Free Dodger Stadium Express shuttle departs from here',
  },
  {
    id: 'rail-pico',
    type: 'rail',
    name: 'Pico Station',
    lat: 34.0394,
    lng: -118.2657,
    venueIds: [4, 5],
    lines: ['A Line (Blue)', 'E Line (Expo)'],
    walkMin: 2,
  },
  {
    id: 'rail-memorial-park',
    type: 'rail',
    name: 'Memorial Park Station',
    lat: 34.1481,
    lng: -118.1316,
    venueIds: [6],
    lines: ['A Line (Blue)'],
    walkMin: 42,
    note: 'Event shuttle service to Rose Bowl during games',
  },

  // ── Bus Stops ────────────────────────────────────────────────────────────────

  {
    id: 'bus-vermont-expo',
    type: 'bus',
    name: 'Vermont/Exposition',
    lat: 34.0168,
    lng: -118.2906,
    venueIds: [1],
    lines: ['Metro 102', 'Metro 204'],
    walkMin: 7,
  },
  {
    id: 'bus-fig-expo',
    type: 'bus',
    name: 'Figueroa/Exposition',
    lat: 34.0163,
    lng: -118.2773,
    venueIds: [1],
    lines: ['Metro 81'],
    walkMin: 11,
  },
  {
    id: 'bus-prairie-kelso',
    type: 'bus',
    name: 'Prairie Ave & Kelso',
    lat: 33.9530,
    lng: -118.3529,
    venueIds: [2],
    lines: ['Metro 115', 'Metro 212'],
    walkMin: 2,
  },
  {
    id: 'bus-sunset-dodger',
    type: 'bus',
    name: 'Sunset Blvd (near Dodger)',
    lat: 34.0764,
    lng: -118.2399,
    venueIds: [3],
    lines: ['Metro 2', 'Metro 302'],
    walkMin: 15,
  },
  {
    id: 'bus-fig-12th',
    type: 'bus',
    name: 'Figueroa & 12th St',
    lat: 34.0409,
    lng: -118.2666,
    venueIds: [4, 5],
    lines: ['Metro 81', 'Metro 62'],
    walkMin: 1,
  },
  {
    id: 'bus-colorado-arroyo',
    type: 'bus',
    name: 'Colorado Blvd & Arroyo Pkwy',
    lat: 34.1474,
    lng: -118.1644,
    venueIds: [6],
    lines: ['Foothill Transit 187', 'Metro 485'],
    walkMin: 27,
  },

  // ── Metro Bike Share Docks ───────────────────────────────────────────────────

  {
    id: 'bike-fig-11th',
    type: 'bike',
    name: 'Metro Bike Share: Figueroa & 11th',
    lat: 34.0419,
    lng: -118.2665,
    venueIds: [4, 5],
    providers: ['Metro Bike Share'],
  },
  {
    id: 'bike-fig-pico',
    type: 'bike',
    name: 'Metro Bike Share: Figueroa & Pico',
    lat: 34.0395,
    lng: -118.2663,
    venueIds: [4, 5],
    providers: ['Metro Bike Share'],
  },
  {
    id: 'bike-pico-flower',
    type: 'bike',
    name: 'Metro Bike Share: Pico & Flower',
    lat: 34.0393,
    lng: -118.2625,
    venueIds: [4, 5],
    providers: ['Metro Bike Share'],
  },

  // ── Scooter Zones ────────────────────────────────────────────────────────────

  {
    id: 'scooter-expo-usc',
    type: 'scooter',
    name: 'Scooters near Expo Park/USC Station',
    lat: 34.0188,
    lng: -118.2854,
    venueIds: [1],
    providers: ['Lime'],
  },
  {
    id: 'scooter-vermont-expo',
    type: 'scooter',
    name: 'Vermont & Exposition — Scooters',
    lat: 34.0168,
    lng: -118.2908,
    venueIds: [1],
    providers: ['Lime', 'Bird'],
    note: 'DoorDash bike dock also available at Vermont & Expo (Arco)',
  },

  // ── Rideshare / Curb Drop-off Zones ─────────────────────────────────────────

  {
    id: 'dropoff-coliseum',
    type: 'dropoff',
    name: 'Vermont Ave Pickup Zone',
    lat: 34.0183,
    lng: -118.2908,
    venueIds: [1],
    note: 'Uber/Lyft pickup on Vermont Ave between Exposition Blvd and Downey Way',
  },
  {
    id: 'dropoff-sofi',
    type: 'dropoff',
    name: 'SoFi Rideshare Zone',
    lat: 33.9562,
    lng: -118.3434,
    venueIds: [2],
    note: 'Kareem Ct & Manchester Blvd. Access via Crenshaw Blvd → westbound Pincay Dr',
  },
  {
    id: 'dropoff-dodger',
    type: 'dropoff',
    name: 'Dodger Stadium Lot 1 Pickup',
    lat: 34.0773,
    lng: -118.2442,
    venueIds: [3],
    note: 'Official Uber pickup zone — Lot 1 via Gate B. Enter from Vin Scully Ave',
  },
  {
    id: 'dropoff-dtla-chickhearn',
    type: 'dropoff',
    name: 'Chick Hearn Ct Pickup Zone',
    lat: 34.0430,
    lng: -118.2692,
    venueIds: [4, 5],
    note: 'White zone, eastbound between LA Live Way and Georgia St',
  },
  {
    id: 'dropoff-dtla-fig',
    type: 'dropoff',
    name: 'Figueroa St Pickup Zone',
    lat: 34.0400,
    lng: -118.2666,
    venueIds: [4, 5],
    note: 'White zone, southbound between 12th St and Pico Blvd',
  },
  {
    id: 'dropoff-rosebowl',
    type: 'dropoff',
    name: 'Old Town Pasadena Pickup',
    lat: 34.1472,
    lng: -118.1303,
    venueIds: [6],
    note: 'Uber/Lyft pickup in Old Town Pasadena; shuttle to Parsons Lot B for events',
  },
];
