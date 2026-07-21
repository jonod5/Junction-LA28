/// <reference types="google.maps" />
// Unified planner (web) — merges the old Builder + Map + Routes/Comparison
// screens into one full-bleed map page (FR-U1–U5). Reference: Google Maps /
// Uber UX — search + itinerary in a floating top-left panel, layer legend
// bottom-left, map fills the rest.
//
// Routing now goes entirely through POST /api/routes/optimize (the Phase 2
// engine) instead of the old per-mode /api/directions button flow — so this
// screen renders the SELECTED ranked option's legs, not a manually-fetched
// single Directions result. Native keeps its existing separate Builder/Map/
// Routes/Comparison screens unchanged (see (tabs)/index.tsx, map.tsx).
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { DeepLinkButtons } from '@/components/DeepLinkButtons';
import { ModePreferencesChecklist } from '@/components/ModePreferencesChecklist';
import { PolicyBanner } from '@/components/PolicyBanner';
import { StopSearch, type SearchItem } from '@/components/StopSearch';
import { AIRPORTS } from '@/constants/airports';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import {
  TRANSIT_LAYER_CONFIG,
  VENUE_TRANSIT,
  type TransitLayer,
  type VenueTransitPoint,
} from '@/constants/venue-transit';
import { VENUES } from '@/constants/venues';
import {
  api,
  DirectionStep,
  RouteMode,
  RouteOption,
  type MicromobilityItem,
} from '@/lib/api';
import { linksForModes, type Place } from '@/lib/deeplinks';
import { decodePolyline, formatDistance, formatDuration } from '@/lib/polyline';
import { ROUTE_MODES, useTrip } from '@/lib/store';

const MAPS_KEY = process.env.EXPO_PUBLIC_GOOGLE_MAPS_KEY ?? '';
const GAMES_POLICY =
  'No spectator parking at venues during LA28 Games. Attendees must use transit, sanctioned park-and-ride, or active transport.';

declare global {
  interface Window {
    google: typeof google;
    __gmCb?: () => void;
  }
}

function loadGoogleMaps(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.maps) { resolve(); return; }
    window.__gmCb = resolve;
    const s = document.createElement('script');
    s.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_KEY}&callback=__gmCb`;
    s.async = true;
    s.onerror = () => reject(new Error('Failed to load Google Maps'));
    document.head.appendChild(s);
  });
}

function toLngLat(encoded: string) {
  return decodePolyline(encoded).map((p) => ({ lat: p.latitude, lng: p.longitude }));
}

// ── Route-mode colors/labels (mirrors app/services/route_engine.MODE_LABEL) ──
const MODE_COLORS: Record<string, string> = {
  walk: colors.primary,
  transit: colors.secondary,
  bike: '#0891B2',
  scooter: '#4D7C0F',
  ebike: '#7C3AED',
  ridehail: colors.accent,
  metro_micro: '#B45309',
};
const MODE_LABELS: Record<string, string> = {
  walk: 'Walk', bike: 'Bike', scooter: 'Scooter', transit: 'Transit',
  metro_micro: 'Metro Micro', ridehail: 'Rideshare',
};

interface RenderStep extends DirectionStep {
  engineMode: string;
}

function makeBadgeIcon(text: string, bg: string): google.maps.Icon {
  const w = Math.max(32, text.length * 8 + 18);
  const h = 22;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <rect rx="11" ry="11" width="${w}" height="${h}" fill="${bg}" stroke="white" stroke-width="1.5"/>
    <text x="${w / 2}" y="15" text-anchor="middle" fill="white"
      font-size="11" font-weight="bold" font-family="system-ui,sans-serif">${text}</text>
  </svg>`;
  return {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new window.google.maps.Size(w, h),
    anchor: new window.google.maps.Point(w / 2, h / 2),
  };
}

function makeTransitIcon(type: TransitLayer): google.maps.Icon {
  const { label, fill } = TRANSIT_LAYER_CONFIG[type];
  const size = 22;
  const r = size / 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
    <circle cx="${r}" cy="${r}" r="${r - 1.5}" fill="${fill}" stroke="white" stroke-width="2"/>
    <text x="${r}" y="${r + 4}" text-anchor="middle" fill="white"
      font-size="10" font-weight="bold" font-family="system-ui,sans-serif">${label}</text>
  </svg>`;
  return {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new window.google.maps.Size(size, size),
    anchor: new window.google.maps.Point(r, r),
  };
}

// Light outline pin for a venue/airport not yet added to the trip — click adds it.
function makeCandidateIcon(kind: 'venue' | 'airport'): google.maps.Icon {
  const fill = kind === 'venue' ? colors.primary : colors.secondary;
  const size = 16;
  const r = size / 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
    <circle cx="${r}" cy="${r}" r="${r - 2}" fill="#fff" stroke="${fill}" stroke-width="2"/>
  </svg>`;
  return {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new window.google.maps.Size(size, size),
    anchor: new window.google.maps.Point(r, r),
  };
}

// Live GBFS micromobility — distinct look from the static hand-collected zones.
const LIVE_COLORS: Record<MicromobilityItem['vehicle_type'], string> = {
  scooter: '#4D7C0F', bike: '#0891B2', ebike: '#7C3AED',
};
const LIVE_GLYPH: Record<MicromobilityItem['vehicle_type'], string> = {
  scooter: 'S', bike: 'B', ebike: 'E',
};
function liveItemCount(item: MicromobilityItem): number | null {
  if (item.kind !== 'station') return null;
  return (item.num_bikes_available ?? 0) + (item.num_ebikes_available ?? 0);
}
function makeLiveIcon(item: MicromobilityItem): google.maps.Icon {
  const fill = LIVE_COLORS[item.vehicle_type] ?? colors.secondary;
  const count = liveItemCount(item);
  const text = count != null ? String(count) : LIVE_GLYPH[item.vehicle_type];
  const size = 20;
  const r = size / 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
    <rect x="2" y="2" width="${size - 4}" height="${size - 4}" rx="4"
      transform="rotate(45 ${r} ${r})" fill="${fill}" stroke="white" stroke-width="2"/>
    <text x="${r}" y="${r + 3.5}" text-anchor="middle" fill="white"
      font-size="9" font-weight="bold" font-family="system-ui,sans-serif">${text}</text>
  </svg>`;
  return {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new window.google.maps.Size(size, size),
    anchor: new window.google.maps.Point(r, r),
  };
}
const LIVE_TYPE_LABEL: Record<MicromobilityItem['vehicle_type'], string> = {
  scooter: 'Scooter', bike: 'Bike', ebike: 'E-bike',
};
function liveInfoHtml(item: MicromobilityItem): string {
  const fill = LIVE_COLORS[item.vehicle_type] ?? colors.secondary;
  const providerName = item.provider.split('-').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  const count = liveItemCount(item);
  return [
    `<div style="font-family:system-ui,sans-serif;max-width:220px;line-height:1.5;padding:2px 0">`,
    `<div style="display:inline-block;background:${fill};color:#fff;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700;margin-bottom:5px">LIVE · ${LIVE_TYPE_LABEL[item.vehicle_type]}</div>`,
    `<div style="font-size:12px;font-weight:700;color:#1F2937">${item.name ?? providerName}</div>`,
    `<div style="font-size:11px;color:#4B5563">${providerName}</div>`,
    item.kind === 'station' && count != null
      ? `<div style="font-size:11px;color:#6B7280;margin-top:2px">${count} available${item.num_docks_available != null ? ` · ${item.num_docks_available} docks` : ''}</div>`
      : `<div style="font-size:11px;color:#6B7280;margin-top:2px">Available now</div>`,
    `<div style="font-size:10px;color:#9CA3AF;margin-top:3px">${Math.round(item.distance_m)} m away · GBFS</div>`,
    `</div>`,
  ].join('');
}

const VENUE_NAME: Record<number, string> = {
  1: 'LA Memorial Coliseum', 2: 'SoFi Stadium', 3: 'Dodger Stadium',
  4: 'Crypto.com Arena', 5: 'Peacock Theater', 6: 'Rose Bowl',
};

function transitInfoHtml(point: VenueTransitPoint): string {
  const { fill, displayName } = TRANSIT_LAYER_CONFIG[point.type];
  const venueLabel = point.venueIds.map((id) => VENUE_NAME[id]).filter(Boolean).join(' · ');
  return [
    `<div style="font-family:system-ui,sans-serif;max-width:230px;line-height:1.5;padding:2px 0">`,
    `<div style="display:inline-block;background:${fill};color:#fff;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700;margin-bottom:5px">${displayName}</div>`,
    `<div style="font-size:12px;font-weight:700;color:#1F2937;margin-bottom:2px">${point.name}</div>`,
    point.lines?.length ? `<div style="font-size:11px;color:#4B5563">${point.lines.join(' · ')}</div>` : '',
    point.providers?.length ? `<div style="font-size:11px;color:#4B5563">${point.providers.join(' · ')}</div>` : '',
    point.walkMin != null
      ? `<div style="font-size:11px;color:#6B7280;margin-top:2px">🚶 ${point.walkMin} min · ${venueLabel}</div>`
      : venueLabel ? `<div style="font-size:11px;color:#6B7280;margin-top:2px">Near: ${venueLabel}</div>` : '',
    point.note ? `<div style="font-size:11px;color:#9CA3AF;margin-top:3px">${point.note}</div>` : '',
    `</div>`,
  ].join('');
}

const WALK_DASH = { path: 'M 0,-1 0,1', strokeOpacity: 0.85, strokeColor: colors.primary, scale: 3 };

function hoverHtml(step: RenderStep): string {
  if (step.mode === 'walking') {
    const dist = step.distance_m > 0 ? formatDistance(step.distance_m) : '';
    const dur = step.duration_s > 0 ? formatDuration(step.duration_s) : '';
    const meta = [dist, dur].filter(Boolean).join(' · ');
    return `<div style="font-family:system-ui,sans-serif;max-width:220px;line-height:1.5">
      <div style="font-size:12px;font-weight:600;color:#1F2937">${step.instruction || 'Walk'}</div>
      ${meta ? `<div style="font-size:11px;color:#6B7280;margin-top:2px">${meta}</div>` : ''}
    </div>`;
  }
  if (step.mode === 'transit') {
    const color = step.transit_color || colors.secondary;
    return `<div style="font-family:system-ui,sans-serif;max-width:240px;line-height:1.5">
      <div style="display:inline-block;background:${color};color:#fff;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700;margin-bottom:5px">
        ${step.transit_line_short ?? step.transit_line ?? 'Transit'}
      </div>
      <div style="font-size:12px;font-weight:600;color:#1F2937">${step.transit_line ?? ''}${step.headsign ? ` → ${step.headsign}` : ''}</div>
      ${step.departure_stop ? `<div style="font-size:11px;color:#555;margin-top:3px">🚉 Board: <b>${step.departure_stop}</b></div>` : ''}
      ${step.arrival_stop ? `<div style="font-size:11px;color:#555">🚉 Exit: <b>${step.arrival_stop}</b></div>` : ''}
      ${step.num_stops != null ? `<div style="font-size:11px;color:#9CA3AF;margin-top:2px">${step.num_stops} stop${step.num_stops !== 1 ? 's' : ''} · ${formatDuration(step.duration_s)}</div>` : ''}
    </div>`;
  }
  // Bicycling/driving Directions step, colored by the ENGINE mode that wraps it
  // (bike/scooter/ridehail/metro_micro), not the raw Google travel mode.
  const label = MODE_LABELS[step.engineMode] ?? step.mode;
  const color = MODE_COLORS[step.engineMode] ?? '#9CA3AF';
  const dist = step.distance_m > 0 ? formatDistance(step.distance_m) : '';
  const dur = step.duration_s > 0 ? formatDuration(step.duration_s) : '';
  return `<div style="font-family:system-ui,sans-serif;max-width:220px;line-height:1.5">
    <div style="display:inline-block;background:${color};color:#fff;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700;margin-bottom:5px">${label}</div>
    <div style="font-size:11px;color:#6B7280">${[dist, dur].filter(Boolean).join(' · ')}</div>
  </div>`;
}

// ── Step row (turn-by-turn, shown when a leg card is expanded) ────────────────
function StepRow({ step }: { step: RenderStep }) {
  if (step.mode === 'transit') {
    const color = step.transit_color ?? colors.secondary;
    const label = step.transit_line_short ?? step.transit_line ?? '';
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
        <div style={{ background: color, color: '#fff', borderRadius: 10, padding: '2px 7px', fontSize: 11, fontFamily: 'Barlow_700Bold', fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0, marginTop: 1 }}>
          {label || '●'}
        </div>
        <div>
          <div style={{ fontSize: 12, fontFamily: 'Barlow_600SemiBold', fontWeight: 600, color: '#1F2937', lineHeight: '1.4' }}>
            {step.transit_line}{step.headsign ? ` → ${step.headsign}` : ''}
          </div>
          {(step.departure_stop || step.arrival_stop) && (
            <div style={{ fontSize: 11, fontFamily: 'Barlow_400Regular', color: '#6B7280', marginTop: 1 }}>
              {step.departure_stop ? `Board: ${step.departure_stop}` : ''}
              {step.departure_stop && step.arrival_stop ? ' · ' : ''}
              {step.arrival_stop ? `Exit: ${step.arrival_stop}` : ''}
            </div>
          )}
        </div>
      </div>
    );
  }
  const color = step.mode === 'walking' ? colors.primary : (MODE_COLORS[step.engineMode] ?? '#9CA3AF');
  const label = step.mode === 'walking' ? step.instruction || 'Walk' : (MODE_LABELS[step.engineMode] ?? step.mode);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
      <div style={{ width: 18, height: 18, borderRadius: '50%', background: color, flexShrink: 0, marginTop: 2 }} />
      <div>
        <div style={{ fontSize: 12, fontFamily: 'Barlow_500Medium', color: '#374151', lineHeight: '1.4' }}>{label}</div>
        <div style={{ fontSize: 11, fontFamily: 'Barlow_400Regular', color: '#9CA3AF' }}>
          {[step.distance_m > 0 ? formatDistance(step.distance_m) : '', step.duration_s > 0 ? formatDuration(step.duration_s) : ''].filter(Boolean).join(' · ')}
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function UnifiedPlannerScreen() {
  const {
    trip, loading, error, clearError, createTrip, addStop, removeStop, reorderStops,
    preferences, setPreferences,
    routeOptions, routeOptionsLoading, routeOptionsError, selectedOptionId,
    optimizeLeg, selectRouteOption,
  } = useTrip();
  const router = useRouter();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const candidateMarkersRef = useRef<google.maps.Marker[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const clickWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const hoverWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transitMarkersRef = useRef<google.maps.Marker[]>([]);
  const liveMarkersRef = useRef<google.maps.Marker[]>([]);

  const [mapError, setMapError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [layerVisibility, setLayerVisibility] = useState<Record<TransitLayer, boolean>>({
    rail: true, bus: true, bike: true, scooter: true, dropoff: true,
  });
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [liveItems, setLiveItems] = useState<MicromobilityItem[]>([]);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);

  // ── Onboarding (FR-U3): destination search → mode preferences → done ───────
  const [onboardingDone, setOnboardingDone] = useState(false);
  const [wizardStep, setWizardStep] = useState<'destination' | 'preferences'>('destination');
  const [draftPrefs, setDraftPrefs] = useState<RouteMode[]>(ROUTE_MODES);

  const [addingStop, setAddingStop] = useState(false);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [expandedLeg, setExpandedLeg] = useState<string | null>(null);

  // Auto-create a session trip on first load — the unified flow doesn't ask
  // the traveler to name a trip; matches the PRD's first-open flow exactly
  // (destination → preferences → view trip, no naming step).
  useEffect(() => {
    if (!trip && !loading) {
      createTrip('My LA28 Trip');
    }
  }, [trip, loading, createTrip]);

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const addedNames = stops.map((s) => s.name);
  const pairs = stops.slice(0, -1).map((from, i) => ({ from, to: stops[i + 1] }));

  // Auto-compute route options for every consecutive pair once onboarding is
  // done — only pairs that are new or whose cached result used different
  // preferences get (re-)fetched; unaffected legs keep their cached result.
  useEffect(() => {
    if (!onboardingDone || preferences === null) return;
    const sortedPrefs = [...preferences].sort();
    const wantPrefs = sortedPrefs.length ? sortedPrefs : null;
    pairs.forEach(({ from, to }) => {
      const key = `${from.id}-${to.id}`;
      const cached = routeOptions[key];
      const cachedPrefs = cached?.preferences ?? null;
      const stale = JSON.stringify(cachedPrefs) !== JSON.stringify(wantPrefs);
      if (!routeOptionsLoading[key] && (!cached || stale)) {
        optimizeLeg(from, to);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onboardingDone, preferences, stops.map((s) => s.id).join(',')]);

  // Flatten each pair's SELECTED option into a single render-ready step list,
  // tagged with the engine mode that produced each leg (for coloring).
  const renderSteps = useMemo(() => {
    const out: Record<string, RenderStep[]> = {};
    pairs.forEach(({ from, to }) => {
      const key = `${from.id}-${to.id}`;
      const res = routeOptions[key];
      if (!res) return;
      const selId = selectedOptionId[key];
      const option = res.options.find((o) => o.id === selId) ?? res.options[0];
      if (!option) return;
      out[key] = option.legs.flatMap((leg) =>
        leg.steps.map((s) => ({ ...s, engineMode: leg.mode })),
      );
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeOptions, selectedOptionId, stops.map((s) => s.id).join(',')]);

  // ── Google Maps init ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!MAPS_KEY) {
      setMapError('Google Maps API key is not configured. Contact the app administrator.');
      return;
    }
    let cancelled = false;
    loadGoogleMaps()
      .then(() => {
        if (cancelled || !containerRef.current || mapRef.current) return;
        const map = new window.google.maps.Map(containerRef.current, {
          center: { lat: 34.052, lng: -118.243 },
          zoom: 11,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: true,
          gestureHandling: 'greedy',
          styles: MAP_STYLE,
        });
        mapRef.current = map;
        setMapReady(true);
        clickWindowRef.current = new window.google.maps.InfoWindow();
        hoverWindowRef.current = new window.google.maps.InfoWindow({ disableAutoPan: true });
      })
      .catch((e) => setMapError(e.message));
    return () => { cancelled = true; };
  }, []);

  const handleSelectSearchItem = (item: SearchItem) => {
    const venueId = item.kind === 'venue' ? item.id : null;
    addStop(venueId, item.name, item.lat, item.lng);
    setAddingStop(false);
  };

  // ── Added-stop markers + selected-route polylines ───────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps) return;

    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];

    if (stops.length === 0) return;
    const bounds = new window.google.maps.LatLngBounds();

    const cancelClose = () => { if (closeTimerRef.current) clearTimeout(closeTimerRef.current); };
    const scheduleClose = () => { closeTimerRef.current = setTimeout(() => hoverWindowRef.current?.close(), 180); };
    const openHover = (content: string, pos: google.maps.LatLng) => {
      cancelClose();
      hoverWindowRef.current?.setContent(content);
      hoverWindowRef.current?.setPosition(pos);
      hoverWindowRef.current?.open(map);
    };
    const addHitTarget = (path: { lat: number; lng: number }[], html: string) => {
      const hit = new window.google.maps.Polyline({ path, strokeOpacity: 0, strokeWeight: 16, map, zIndex: 25 });
      hit.addListener('mouseover', (e: google.maps.MapMouseEvent) => { if (e.latLng) openHover(html, e.latLng); });
      hit.addListener('mouseout', scheduleClose);
      polylinesRef.current.push(hit);
    };

    stops.forEach((s, i) => {
      const marker = new window.google.maps.Marker({
        position: { lat: s.lat, lng: s.lng },
        map,
        zIndex: 20,
        label: { text: String(i + 1), color: '#fff', fontWeight: '700', fontSize: '13px' },
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          fillColor: colors.primary, fillOpacity: 1,
          strokeColor: '#fff', strokeWeight: 2.5, scale: 16,
        },
        title: s.name,
      });
      marker.addListener('click', () => {
        const detailsLink = s.venue_id != null
          ? `<div style="margin-top:4px"><a href="/venue/${s.venue_id}" style="font-size:11px;color:${colors.primary};font-weight:600">View venue details →</a></div>`
          : '';
        clickWindowRef.current?.setContent(
          `<div style="font-family:system-ui,sans-serif;padding:3px 2px">
            <b style="font-size:13px">${i + 1}. ${s.name}</b>${detailsLink}
          </div>`,
        );
        clickWindowRef.current?.open(map, marker);
      });
      markersRef.current.push(marker);
      bounds.extend({ lat: s.lat, lng: s.lng });
    });

    pairs.forEach(({ from, to }) => {
      const key = `${from.id}-${to.id}`;
      const steps = renderSteps[key] ?? [];
      steps.forEach((step) => {
        if (!step.polyline) return;
        const path = toLngLat(step.polyline);
        if (path.length === 0) return;
        const html = hoverHtml(step);

        if (step.mode === 'walking') {
          const poly = new window.google.maps.Polyline({
            path, geodesic: true, strokeOpacity: 0, strokeWeight: 3,
            icons: [{ icon: WALK_DASH, offset: '0', repeat: '12px' }],
            map, zIndex: 5,
          });
          polylinesRef.current.push(poly);
          addHitTarget(path, html);
        } else if (step.mode === 'transit') {
          const lineColor = step.transit_color || colors.secondary;
          const outline = new window.google.maps.Polyline({ path, geodesic: true, strokeColor: '#fff', strokeOpacity: 0.55, strokeWeight: 9, map, zIndex: 8 });
          const poly = new window.google.maps.Polyline({ path, geodesic: true, strokeColor: lineColor, strokeOpacity: 1, strokeWeight: 6, map, zIndex: 9 });
          polylinesRef.current.push(outline, poly);
          const openClick = (pos: google.maps.LatLng | null | undefined) => {
            clickWindowRef.current?.setContent(html);
            clickWindowRef.current?.setPosition(pos ?? path[Math.floor(path.length / 2)]);
            clickWindowRef.current?.open(map);
          };
          poly.addListener('click', (e: google.maps.MapMouseEvent) => openClick(e.latLng));
          addHitTarget(path, html);
          const label = step.transit_line_short ?? (step.transit_line?.slice(0, 8) ?? '');
          if (label) {
            const mid = path[Math.floor(path.length / 2)];
            const badge = new window.google.maps.Marker({ position: mid, map, icon: makeBadgeIcon(label, lineColor), title: step.transit_line ?? '', zIndex: 15, optimized: false });
            badge.addListener('click', () => openClick(badge.getPosition()));
            markersRef.current.push(badge);
          }
        } else {
          const color = MODE_COLORS[step.engineMode] ?? '#9CA3AF';
          const poly = new window.google.maps.Polyline({ path, geodesic: true, strokeColor: color, strokeOpacity: 0.85, strokeWeight: 5, map, zIndex: 6 });
          polylinesRef.current.push(poly);
          addHitTarget(path, html);
        }
      });
    });

    if (stops.length === 1) {
      map.setCenter({ lat: stops[0].lat, lng: stops[0].lng });
      map.setZoom(14);
    } else {
      map.fitBounds(bounds, 80);
    }
  }, [stops, renderSteps]);

  // ── Candidate markers — venues/airports NOT yet added; click adds them ───
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    candidateMarkersRef.current.forEach((m) => m.setMap(null));
    candidateMarkersRef.current = [];

    const candidates: SearchItem[] = [...VENUES, ...AIRPORTS].filter((item) => !addedNames.includes(item.name));
    candidates.forEach((item) => {
      const marker = new window.google.maps.Marker({
        position: { lat: item.lat, lng: item.lng },
        map,
        icon: makeCandidateIcon(item.kind),
        title: `Add ${item.name}`,
        zIndex: 10,
        optimized: false,
      });
      marker.addListener('click', () => handleSelectSearchItem(item));
      candidateMarkersRef.current.push(marker);
    });
    return () => {
      candidateMarkersRef.current.forEach((m) => m.setMap(null));
      candidateMarkersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReady, addedNames.join(',')]);

  // ── Static transit overlay (hand-collected zones — always-on fallback) ───
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    transitMarkersRef.current.forEach((m) => m.setMap(null));
    transitMarkersRef.current = [];
    VENUE_TRANSIT.forEach((point) => {
      if (!layerVisibility[point.type]) return;
      const marker = new window.google.maps.Marker({ position: { lat: point.lat, lng: point.lng }, map, icon: makeTransitIcon(point.type), title: point.name, zIndex: 12, optimized: false });
      marker.addListener('click', () => {
        clickWindowRef.current?.setContent(transitInfoHtml(point));
        clickWindowRef.current?.open(map, marker);
      });
      transitMarkersRef.current.push(marker);
    });
    return () => { transitMarkersRef.current.forEach((m) => m.setMap(null)); transitMarkersRef.current = []; };
  }, [mapReady, layerVisibility]);

  // ── Live GBFS overlay ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!liveEnabled) { setLiveItems([]); setLiveError(null); return; }
    let cancelled = false;
    setLiveLoading(true);
    setLiveError(null);
    Promise.all(VENUES.map((v) => api.getMicromobility(v.lat, v.lng, 800).catch(() => null)))
      .then((results) => {
        if (cancelled) return;
        const seen = new Set<string>();
        const merged: MicromobilityItem[] = [];
        let anyOk = false;
        for (const res of results) {
          if (!res) continue;
          anyOk = true;
          for (const item of res.items) {
            const key = `${item.provider}:${item.kind}:${item.id ?? `${item.lat},${item.lng}`}`;
            if (seen.has(key)) continue;
            seen.add(key);
            merged.push(item);
          }
        }
        setLiveItems(merged);
        setLiveError(anyOk ? null : 'Live feeds unavailable — showing static zones');
      })
      .finally(() => { if (!cancelled) setLiveLoading(false); });
    return () => { cancelled = true; };
  }, [liveEnabled]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    liveMarkersRef.current.forEach((m) => m.setMap(null));
    liveMarkersRef.current = [];
    if (!liveEnabled) return;
    liveItems.forEach((item) => {
      const marker = new window.google.maps.Marker({ position: { lat: item.lat, lng: item.lng }, map, icon: makeLiveIcon(item), title: item.name ?? item.provider, zIndex: 14, optimized: false });
      marker.addListener('click', () => { clickWindowRef.current?.setContent(liveInfoHtml(item)); clickWindowRef.current?.open(map, marker); });
      liveMarkersRef.current.push(marker);
    });
    return () => { liveMarkersRef.current.forEach((m) => m.setMap(null)); liveMarkersRef.current = []; };
  }, [mapReady, liveEnabled, liveItems]);

  // ── Panel actions ─────────────────────────────────────────────────────────
  const moveStop = (index: number, dir: -1 | 1) => {
    const target = index + dir;
    if (target < 0 || target >= stops.length) return;
    const reordered = [...stops];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    reorderStops(reordered.map((s, i) => ({ stop_id: s.id, order_index: i })));
  };

  const finishOnboarding = () => {
    setPreferences(draftPrefs);
    setOnboardingDone(true);
  };

  const totalMinutes = pairs.reduce((sum, { from, to }) => {
    const key = `${from.id}-${to.id}`;
    const res = routeOptions[key];
    const opt = res?.options.find((o) => o.id === selectedOptionId[key]) ?? res?.options[0];
    return sum + (opt?.total_minutes ?? 0);
  }, 0);
  const totalCost = pairs.reduce((sum, { from, to }) => {
    const key = `${from.id}-${to.id}`;
    const res = routeOptions[key];
    const opt = res?.options.find((o) => o.id === selectedOptionId[key]) ?? res?.options[0];
    return sum + (opt?.total_cost_usd ?? 0);
  }, 0);

  return (
    <View style={styles.wrapper}>
      <div ref={containerRef as React.RefObject<HTMLDivElement>} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />

      {/* ── Map layers legend (bottom-left) ──────────────────────────────── */}
      {!mapError && (
        <div style={LEGEND_STYLE}>
          <div style={{ ...LEGEND_LABEL, fontSize: 9, color: '#9CA3AF', letterSpacing: '0.06em', marginBottom: 4 }}>NEARBY</div>
          {(Object.keys(TRANSIT_LAYER_CONFIG) as TransitLayer[]).map((layer) => {
            const { label, fill, displayName } = TRANSIT_LAYER_CONFIG[layer];
            const active = layerVisibility[layer];
            return (
              <div key={layer} onClick={() => setLayerVisibility((prev) => ({ ...prev, [layer]: !prev[layer] }))} style={{ ...LEGEND_ROW, cursor: 'pointer', opacity: active ? 1 : 0.4 }}>
                <div style={{ width: 18, height: 18, borderRadius: '50%', background: active ? fill : '#9CA3AF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <span style={{ fontSize: 9, color: '#fff', fontWeight: 700, fontFamily: 'system-ui,sans-serif' }}>{label}</span>
                </div>
                <span style={{ ...LEGEND_LABEL, fontSize: 11, color: active ? '#374151' : '#9CA3AF' }}>{displayName}</span>
              </div>
            );
          })}
          <div style={{ borderTop: '1px solid #E5E7EB', marginTop: 4, marginBottom: 4 }} />
          <div style={{ ...LEGEND_LABEL, fontSize: 9, color: '#9CA3AF', letterSpacing: '0.06em', marginBottom: 4 }}>LIVE</div>
          <div onClick={() => setLiveEnabled((v) => !v)} style={{ ...LEGEND_ROW, cursor: 'pointer', opacity: liveEnabled ? 1 : 0.5 }}>
            <div style={{ width: 18, height: 18, background: liveEnabled ? LIVE_COLORS.scooter : '#9CA3AF', transform: 'rotate(45deg)', borderRadius: 3, flexShrink: 0 }} />
            <span style={{ ...LEGEND_LABEL, fontSize: 11, color: liveEnabled ? '#374151' : '#9CA3AF' }}>Bikes &amp; scooters</span>
          </div>
          {liveEnabled && (
            <div style={{ ...LEGEND_LABEL, fontSize: 10, color: '#9CA3AF', maxWidth: 130, lineHeight: '1.3', marginTop: 2 }}>
              {liveLoading ? 'Loading live availability…' : liveError ?? `${liveItems.length} nearby · updates on refresh`}
            </div>
          )}
        </div>
      )}

      {/* ── Main floating panel (top-left) ───────────────────────────────── */}
      {!mapError && (
        <div style={PANEL_STYLE}>
          <View style={styles.panelHeader}>
            <Text style={styles.panelTitle}>LA28 PLANNER</Text>
          </View>
          <View style={{ marginBottom: spacing.sm }}>
            <PolicyBanner text={GAMES_POLICY} compact />
          </View>

          {error && (
            <Pressable onPress={clearError} style={styles.errorBanner}>
              <Feather name="alert-circle" size={13} color={colors.destructive} />
              <Text style={styles.errorBannerText}>{error}</Text>
            </Pressable>
          )}

          {!onboardingDone ? (
            wizardStep === 'destination' ? (
              <View style={{ gap: spacing.sm }}>
                <Text style={styles.stepTitle}>Where do you want to go?</Text>
                <Text style={styles.stepHint}>Add every venue or airport on your trip — search below or click a marker on the map.</Text>
                <StopSearch addedNames={addedNames} onSelect={handleSelectSearchItem} />
                {stops.length > 0 && (
                  <View style={{ gap: 4, marginTop: spacing.xs }}>
                    {stops.map((s, i) => (
                      <View key={s.id} style={styles.miniStopRow}>
                        <View style={styles.miniStopBadge}><Text style={styles.miniStopBadgeText}>{i + 1}</Text></View>
                        <Text style={styles.miniStopName} numberOfLines={1}>{s.name}</Text>
                        <Pressable onPress={() => removeStop(s.id)} hitSlop={8} accessibilityLabel={`Remove ${s.name}`}>
                          <Feather name="x" size={14} color={colors.mutedFg} />
                        </Pressable>
                      </View>
                    ))}
                  </View>
                )}
                <Pressable
                  onPress={() => setWizardStep('preferences')}
                  disabled={stops.length === 0}
                  accessibilityRole="button"
                  style={({ pressed }) => [styles.primaryBtn, stops.length === 0 && styles.primaryBtnDisabled, pressed && { opacity: 0.85 }]}
                >
                  <Text style={styles.primaryBtnText}>Next</Text>
                  <Feather name="arrow-right" size={15} color={colors.onPrimary} />
                </Pressable>
              </View>
            ) : (
              <View style={{ gap: spacing.sm }}>
                <Text style={styles.stepTitle}>Which ways are you open to traveling?</Text>
                <Text style={styles.stepHint}>We'll rank real routes across whatever you allow.</Text>
                <ModePreferencesChecklist selected={draftPrefs} onChange={setDraftPrefs} />
                <View style={{ flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs }}>
                  <Pressable onPress={() => setWizardStep('destination')} accessibilityRole="button" style={({ pressed }) => [styles.secondaryBtn, pressed && { opacity: 0.85 }]}>
                    <Feather name="arrow-left" size={14} color={colors.primary} />
                    <Text style={styles.secondaryBtnText}>Back</Text>
                  </Pressable>
                  <Pressable
                    onPress={finishOnboarding}
                    disabled={draftPrefs.length === 0}
                    accessibilityRole="button"
                    style={({ pressed }) => [styles.primaryBtn, { flex: 1 }, draftPrefs.length === 0 && styles.primaryBtnDisabled, pressed && { opacity: 0.85 }]}
                  >
                    <Text style={styles.primaryBtnText}>View Trip</Text>
                  </Pressable>
                </View>
                {draftPrefs.length === 0 && <Text style={styles.stepHint}>Select at least one way to travel.</Text>}
              </View>
            )
          ) : (
            <View style={{ gap: spacing.sm }}>
              {/* Summary + preferences toggle */}
              <View style={styles.summaryRow}>
                <Text style={styles.summaryText}>
                  {stops.length} stops{totalMinutes > 0 ? ` · ${formatDuration(totalMinutes * 60)}` : ''}{totalCost > 0 ? ` · ~$${totalCost.toFixed(2)}` : ''}
                </Text>
                <Pressable onPress={() => setPrefsOpen((v) => !v)} accessibilityRole="button" style={styles.gearBtn}>
                  <Feather name="sliders" size={14} color={colors.primary} />
                </Pressable>
              </View>
              {prefsOpen && (
                <View style={styles.prefsPanel}>
                  <ModePreferencesChecklist
                    selected={preferences ?? ROUTE_MODES}
                    onChange={setPreferences}
                  />
                </View>
              )}

              {/* Stop list */}
              <View style={{ gap: 6 }}>
                {stops.map((s, i) => (
                  <View key={s.id} style={styles.stopRow}>
                    <View style={styles.miniStopBadge}><Text style={styles.miniStopBadgeText}>{i + 1}</Text></View>
                    <Text style={styles.miniStopName} numberOfLines={1}>{s.name}</Text>
                    <Pressable onPress={() => moveStop(i, -1)} disabled={i === 0} hitSlop={6} accessibilityLabel={`Move ${s.name} up`}>
                      <Feather name="chevron-up" size={15} color={i === 0 ? colors.border : colors.muted} />
                    </Pressable>
                    <Pressable onPress={() => moveStop(i, 1)} disabled={i === stops.length - 1} hitSlop={6} accessibilityLabel={`Move ${s.name} down`}>
                      <Feather name="chevron-down" size={15} color={i === stops.length - 1 ? colors.border : colors.muted} />
                    </Pressable>
                    <Pressable onPress={() => removeStop(s.id)} hitSlop={6} accessibilityLabel={`Remove ${s.name}`}>
                      <Feather name="x-circle" size={15} color={colors.mutedFg} />
                    </Pressable>
                  </View>
                ))}
              </View>

              {addingStop ? (
                <StopSearch addedNames={addedNames} onSelect={handleSelectSearchItem} />
              ) : (
                <Pressable onPress={() => setAddingStop(true)} accessibilityRole="button" style={styles.addStopBtn}>
                  <Feather name="plus" size={14} color={colors.primary} />
                  <Text style={styles.addStopText}>Add stop</Text>
                </Pressable>
              )}

              {/* Route options per consecutive leg */}
              {pairs.map(({ from, to }) => {
                const key = `${from.id}-${to.id}`;
                const res = routeOptions[key];
                const isLoading = routeOptionsLoading[key];
                const err = routeOptionsError[key];
                const selId = selectedOptionId[key];
                const originPlace: Place = { lat: from.lat, lng: from.lng, name: from.name };
                const destPlace: Place = { lat: to.lat, lng: to.lng, name: to.name };
                return (
                  <View key={key} style={styles.legCard}>
                    <Text style={styles.legHeader} numberOfLines={1}>{from.name} → {to.name}</Text>
                    {isLoading && <ActivityIndicator color={colors.primary} size="small" style={{ alignSelf: 'flex-start', marginTop: 4 }} />}
                    {err && !isLoading && (
                      <View style={{ gap: 4 }}>
                        <Text style={styles.legError}>{err}</Text>
                        <Pressable onPress={() => optimizeLeg(from, to)} style={styles.secondaryBtn}>
                          <Feather name="refresh-cw" size={12} color={colors.primary} />
                          <Text style={styles.secondaryBtnText}>Retry</Text>
                        </Pressable>
                      </View>
                    )}
                    {res && !isLoading && (
                      <View style={{ gap: 6 }}>
                        {res.options.map((opt: RouteOption, idx: number) => {
                          const active = opt.id === selId;
                          return (
                            <Pressable
                              key={opt.id}
                              onPress={() => selectRouteOption(from.id, to.id, opt.id)}
                              accessibilityRole="button"
                              style={[styles.optionCard, active && styles.optionCardActive]}
                            >
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                                <Text style={[styles.optionLabel, active && styles.optionLabelActive]} numberOfLines={1}>{opt.label}</Text>
                                {idx === 0 && <Text style={styles.bestBadge}>BEST</Text>}
                              </View>
                              <Text style={styles.optionMeta}>
                                {formatDuration(opt.total_minutes * 60)} · ~${opt.total_cost_usd.toFixed(2)}
                                {opt.num_transfers > 0 ? ` · ${opt.num_transfers} transfer${opt.num_transfers === 1 ? '' : 's'}` : ''}
                              </Text>
                            </Pressable>
                          );
                        })}

                        {selId && (
                          <>
                            <Pressable onPress={() => setExpandedLeg(expandedLeg === key ? null : key)} style={styles.stepsToggle}>
                              <Text style={styles.secondaryBtnText}>{expandedLeg === key ? 'Hide steps' : 'Show steps'}</Text>
                              <Feather name={expandedLeg === key ? 'chevron-up' : 'chevron-down'} size={13} color={colors.primary} />
                            </Pressable>
                            {expandedLeg === key && (
                              <div style={{ paddingLeft: 4 }}>
                                {(renderSteps[key] ?? []).map((step, i) => <StepRow key={i} step={step} />)}
                              </div>
                            )}
                            <DeepLinkButtons
                              links={linksForModes(
                                res.options.find((o) => o.id === selId)?.modes ?? [],
                                originPlace, destPlace,
                              )}
                            />
                          </>
                        )}
                      </View>
                    )}
                  </View>
                );
              })}
            </View>
          )}
        </div>
      )}

      {/* Error overlay */}
      {mapError && (
        <View style={styles.overlay}>
          <Feather name="alert-circle" size={32} color={colors.destructive} />
          <Text style={styles.errorText}>{mapError}</Text>
        </View>
      )}
    </View>
  );
}

// ── Legend inline styles ───────────────────────────────────────────────────────

// Bottom-right (not bottom-left) so the wider itinerary panel on the left
// never grows tall enough to cover it. Offset above Google's own bottom-right
// "camera controls" widget so the two don't overlap.
const LEGEND_STYLE: React.CSSProperties = {
  position: 'absolute', bottom: 90, right: 12,
  background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(4px)',
  borderRadius: 10, padding: '10px 12px', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
  display: 'flex', flexDirection: 'column', gap: 7, zIndex: 10,
};
const LEGEND_ROW: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 8 };
const LEGEND_LABEL: React.CSSProperties = { fontFamily: 'Barlow_500Medium', fontSize: 12, color: '#374151', fontWeight: '500' };

const PANEL_STYLE: React.CSSProperties = {
  position: 'absolute', top: 12, left: 12, width: 460,
  maxHeight: 'calc(100% - 24px)', overflowY: 'auto',
  background: 'rgba(255,255,255,0.97)', backdropFilter: 'blur(6px)',
  borderRadius: 14, padding: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.18)', zIndex: 10,
};

// ── Map style ─────────────────────────────────────────────────────────────────

const MAP_STYLE: google.maps.MapTypeStyle[] = [
  { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit.station', elementType: 'labels.icon', stylers: [{ visibility: 'on' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ lightness: 10 }] },
  { featureType: 'road.highway', elementType: 'geometry.fill', stylers: [{ color: '#f3d079' }] },
  { featureType: 'road.arterial', elementType: 'geometry.fill', stylers: [{ color: '#ffffff' }] },
  { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#f5f1eb' }] },
];

// ── RN styles ─────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: colors.background },
  overlay: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    alignItems: 'center', justifyContent: 'center', gap: spacing.md,
    paddingHorizontal: spacing.xl, backgroundColor: colors.background,
  },
  errorText: { fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.destructive, textAlign: 'center', lineHeight: 20 },
  panelHeader: { marginBottom: spacing.xs },
  panelTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 20, color: colors.foreground, letterSpacing: 1 },
  errorBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FEF2F2', borderRadius: radius.sm, padding: spacing.sm, marginBottom: spacing.sm },
  errorBannerText: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.destructive, flex: 1 },
  stepTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 18, color: colors.foreground },
  stepHint: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, lineHeight: 17 },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.sm, minHeight: 44,
  },
  primaryBtnDisabled: { opacity: 0.4 },
  primaryBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 14, color: colors.onPrimary },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 6, paddingHorizontal: spacing.sm, minHeight: 36 },
  secondaryBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.primary },
  miniStopRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: 4 },
  stopRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.mutedBg, borderRadius: radius.sm, padding: 8 },
  miniStopBadge: { width: 20, height: 20, borderRadius: 10, backgroundColor: colors.gold, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  miniStopBadgeText: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 11, color: '#1A0A00' },
  miniStopName: { flex: 1, fontFamily: 'Barlow_500Medium', fontSize: 13, color: colors.foreground },
  addStopBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.sm, paddingVertical: 8, minHeight: 40 },
  addStopText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
  summaryRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  summaryText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.foreground },
  gearBtn: { padding: 6 },
  prefsPanel: { backgroundColor: colors.mutedBg, borderRadius: radius.sm, padding: spacing.sm },
  legCard: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.sm, gap: 6, ...shadow.sm, borderLeftWidth: 3, borderLeftColor: colors.primary },
  legHeader: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.foreground },
  legError: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.destructive },
  optionCard: { borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.sm, padding: 8 },
  optionCardActive: { borderColor: colors.primary, backgroundColor: colors.mutedBg },
  optionLabel: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.foreground, flexShrink: 1 },
  optionLabelActive: { color: colors.primary },
  bestBadge: { fontFamily: 'Barlow_700Bold', fontSize: 9, color: colors.gold, letterSpacing: 0.5 },
  optionMeta: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, marginTop: 2 },
  stepsToggle: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start' },
});
