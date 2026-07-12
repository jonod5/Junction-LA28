/// <reference types="google.maps" />
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { DirectionStep } from '@/lib/api';
import { colors, radius, spacing } from '@/constants/theme';
import { decodePolyline, formatDistance, formatDuration } from '@/lib/polyline';
import { useTrip } from '@/lib/store';
import {
  VENUE_TRANSIT,
  TRANSIT_LAYER_CONFIG,
  type TransitLayer,
  type VenueTransitPoint,
} from '@/constants/venue-transit';

const MAPS_KEY = process.env.EXPO_PUBLIC_GOOGLE_MAPS_KEY ?? '';

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

const VENUE_NAME: Record<number, string> = {
  1: 'LA Memorial Coliseum',
  2: 'SoFi Stadium',
  3: 'Dodger Stadium',
  4: 'Crypto.com Arena',
  5: 'Peacock Theater',
  6: 'Rose Bowl',
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
      : venueLabel
        ? `<div style="font-size:11px;color:#6B7280;margin-top:2px">Near: ${venueLabel}</div>`
        : '',
    point.note ? `<div style="font-size:11px;color:#9CA3AF;margin-top:3px">${point.note}</div>` : '',
    `</div>`,
  ].join('');
}

const WALK_DASH = {
  path: 'M 0,-1 0,1',
  strokeOpacity: 0.85,
  strokeColor: colors.primary,
  scale: 3,
};

function hoverHtml(step: DirectionStep): string {
  if (step.mode === 'walking') {
    const dist = step.distance_m > 0 ? formatDistance(step.distance_m) : '';
    const dur = step.duration_s > 0 ? formatDuration(step.duration_s) : '';
    const meta = [dist, dur].filter(Boolean).join(' · ');
    return `<div style="font-family:system-ui,sans-serif;max-width:220px;line-height:1.5">
      <div style="font-size:12px;font-weight:600;color:#1F2937">${step.instruction || 'Walk'}</div>
      ${meta ? `<div style="font-size:11px;color:#6B7280;margin-top:2px">${meta}</div>` : ''}
      ${step.sub_steps?.length ? `<div style="font-size:11px;color:#9CA3AF;margin-top:3px">${step.sub_steps.slice(0, 3).join('<br>')}</div>` : ''}
    </div>`;
  }
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

function legHoverHtml(mode: string, duration_s: number | null, distance_m: number | null): string {
  const label = mode === 'walking' ? 'Walk' : mode === 'transit' ? 'Transit' : mode;
  return `<div style="font-family:system-ui,sans-serif;font-size:12px;color:#1F2937">
    <b>${label}</b> · ${formatDuration(duration_s ?? 0)} · ${formatDistance(distance_m ?? 0)}
  </div>`;
}

// ── Sheet step row (HTML component) ───────────────────────────────────────────

function SheetStepRow({ step }: { step: DirectionStep }) {
  if (step.mode === 'transit') {
    const color = step.transit_color ?? colors.secondary;
    const label = step.transit_line_short ?? step.transit_line ?? '';
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
        {label ? (
          <div style={{
            background: color, color: '#fff', borderRadius: 10,
            padding: '2px 7px', fontSize: 11, fontWeight: 700,
            whiteSpace: 'nowrap', flexShrink: 0, marginTop: 1,
          }}>
            {label}
          </div>
        ) : (
          <div style={{
            width: 18, height: 18, borderRadius: '50%', background: color,
            flexShrink: 0, marginTop: 2,
          }} />
        )}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#1F2937', lineHeight: '1.4' }}>
            {step.transit_line}{step.headsign ? ` → ${step.headsign}` : ''}
          </div>
          {(step.departure_stop || step.arrival_stop) && (
            <div style={{ fontSize: 11, color: '#6B7280', marginTop: 1 }}>
              {step.departure_stop ? `Board: ${step.departure_stop}` : ''}
              {step.departure_stop && step.arrival_stop ? ' · ' : ''}
              {step.arrival_stop ? `Exit: ${step.arrival_stop}` : ''}
            </div>
          )}
          <div style={{ fontSize: 11, color: '#9CA3AF' }}>
            {step.num_stops != null ? `${step.num_stops} stop${step.num_stops !== 1 ? 's' : ''} · ` : ''}
            {formatDuration(step.duration_s)}
          </div>
        </div>
      </div>
    );
  }
  // Walking / other
  const TURN_ARROWS: Record<string, string> = {
    'turn-left': '↰', 'sharp-left': '↰', 'slight-left': '↖', 'keep-left': '↖',
    'turn-right': '↱', 'sharp-right': '↱', 'slight-right': '↗', 'keep-right': '↗',
    'uturn-left': '↩', 'uturn-right': '↪',
    'merge': '⬆', 'straight': '↑',
    'fork-left': '↖', 'fork-right': '↗',
    'ramp-left': '↖', 'ramp-right': '↗',
    'roundabout-left': '↺', 'roundabout-right': '↻',
  };
  const arrow = step.maneuver ? (TURN_ARROWS[step.maneuver] ?? '↑') : '↑';
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
      <div style={{
        width: 20, height: 20, borderRadius: '50%',
        background: colors.primary,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, marginTop: 1,
      }}>
        <span style={{ fontSize: 11, color: '#fff', lineHeight: 1 }}>{arrow}</span>
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#374151', lineHeight: '1.4' }}>{step.instruction}</div>
        <div style={{ fontSize: 11, color: '#9CA3AF' }}>
          {[
            step.distance_m > 0 ? formatDistance(step.distance_m) : '',
            step.duration_s > 0 ? formatDuration(step.duration_s) : '',
          ].filter(Boolean).join(' · ')}
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function MapWebScreen() {
  const { trip, directionSteps } = useTrip();
  const router = useRouter();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const clickWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const hoverWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transitMarkersRef = useRef<google.maps.Marker[]>([]);

  const [mapError, setMapError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [hasSteps, setHasSteps] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [layerVisibility, setLayerVisibility] = useState<Record<TransitLayer, boolean>>({
    rail: true, bus: true, bike: true, scooter: true, dropoff: true,
  });

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const legs = trip?.legs ?? [];
  const totalDuration = legs.reduce((s, l) => s + (l.duration_s ?? 0), 0);
  const totalDistance = legs.reduce((s, l) => s + (l.distance_m ?? 0), 0);

  // Init Google Maps once
  useEffect(() => {
    if (!MAPS_KEY) {
      setMapError('Add EXPO_PUBLIC_GOOGLE_MAPS_KEY to frontend/.env.local, then restart Metro.');
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

  // Sync markers + polylines whenever trip or directionSteps change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps) return;

    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];

    if (stops.length === 0) return;

    const bounds = new window.google.maps.LatLngBounds();

    // Hover helpers
    const cancelClose = () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
    const scheduleClose = () => {
      closeTimerRef.current = setTimeout(() => hoverWindowRef.current?.close(), 180);
    };
    const openHover = (content: string, pos: google.maps.LatLng) => {
      cancelClose();
      hoverWindowRef.current?.setContent(content);
      hoverWindowRef.current?.setPosition(pos);
      hoverWindowRef.current?.open(map);
    };

    // Helper: add invisible wide hit target for hover
    const addHitTarget = (path: { lat: number; lng: number }[], html: string) => {
      const hit = new window.google.maps.Polyline({
        path, strokeOpacity: 0, strokeWeight: 16, map, zIndex: 25,
      });
      hit.addListener('mouseover', (e: google.maps.MapMouseEvent) => {
        if (e.latLng) openHover(html, e.latLng);
      });
      hit.addListener('mouseout', scheduleClose);
      polylinesRef.current.push(hit);
    };

    // ── Venue markers ──────────────────────────────────────────────────────
    stops.forEach((s, i) => {
      const marker = new window.google.maps.Marker({
        position: { lat: s.lat, lng: s.lng },
        map,
        zIndex: 20,
        label: { text: String(i + 1), color: '#fff', fontWeight: '700', fontSize: '13px' },
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          fillColor: colors.primary,
          fillOpacity: 1,
          strokeColor: '#fff',
          strokeWeight: 2.5,
          scale: 16,
        },
        title: s.name,
      });
      marker.addListener('click', () => {
        clickWindowRef.current?.setContent(
          `<div style="font-family:system-ui,sans-serif;padding:3px 2px">
            <b style="font-size:13px">${i + 1}. ${s.name}</b>
          </div>`,
        );
        clickWindowRef.current?.open(map, marker);
      });
      markersRef.current.push(marker);
      bounds.extend({ lat: s.lat, lng: s.lng });
    });

    // ── Route rendering ────────────────────────────────────────────────────
    const stepKeys = Object.keys(directionSteps);
    const usingSteps = stepKeys.length > 0;
    setHasSteps(usingSteps);

    if (usingSteps) {
      stepKeys.forEach((legKey) => {
        directionSteps[legKey].forEach((step) => {
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

            const outline = new window.google.maps.Polyline({
              path, geodesic: true, strokeColor: '#fff', strokeOpacity: 0.55,
              strokeWeight: 9, map, zIndex: 8,
            });
            const poly = new window.google.maps.Polyline({
              path, geodesic: true, strokeColor: lineColor, strokeOpacity: 1,
              strokeWeight: 6, map, zIndex: 9,
            });
            polylinesRef.current.push(outline, poly);

            // Click shows sticky InfoWindow
            const openClick = (pos: google.maps.LatLng | null | undefined) => {
              clickWindowRef.current?.setContent(html);
              clickWindowRef.current?.setPosition(pos ?? path[Math.floor(path.length / 2)]);
              clickWindowRef.current?.open(map);
            };
            poly.addListener('click', (e: google.maps.MapMouseEvent) => openClick(e.latLng));

            // Hover
            addHitTarget(path, html);

            // Line badge at midpoint
            const label = step.transit_line_short ?? (step.transit_line?.slice(0, 8) ?? '');
            if (label) {
              const mid = path[Math.floor(path.length / 2)];
              const badge = new window.google.maps.Marker({
                position: mid, map,
                icon: makeBadgeIcon(label, lineColor),
                title: step.transit_line ?? '',
                zIndex: 15, optimized: false,
              });
              badge.addListener('click', () => openClick(badge.getPosition()));
              markersRef.current.push(badge);
            }

          } else {
            const poly = new window.google.maps.Polyline({
              path, geodesic: true, strokeColor: '#9CA3AF', strokeOpacity: 0.7,
              strokeWeight: 4, map, zIndex: 5,
            });
            polylinesRef.current.push(poly);
            addHitTarget(path, html);
          }
        });
      });

    } else {
      // Fallback: overview polylines colored by mode
      legs.forEach((leg) => {
        if (!leg.polyline) return;
        const path = toLngLat(leg.polyline);
        const isWalk = leg.mode === 'walking';
        const isTransit = leg.mode === 'transit';
        const html = legHoverHtml(leg.mode, leg.duration_s, leg.distance_m);

        if (isWalk) {
          const poly = new window.google.maps.Polyline({
            path, geodesic: true, strokeOpacity: 0, strokeWeight: 3,
            icons: [{ icon: WALK_DASH, offset: '0', repeat: '12px' }],
            map, zIndex: 5,
          });
          polylinesRef.current.push(poly);
        } else {
          const color = isTransit ? colors.secondary : '#9CA3AF';
          const outline = new window.google.maps.Polyline({
            path, geodesic: true, strokeColor: '#fff', strokeOpacity: 0.55,
            strokeWeight: 9, map, zIndex: 8,
          });
          const poly = new window.google.maps.Polyline({
            path, geodesic: true, strokeColor: color, strokeOpacity: 0.95,
            strokeWeight: 6, map, zIndex: 9,
          });
          polylinesRef.current.push(outline, poly);
        }
        addHitTarget(path, html);
      });
    }

    // Fit bounds
    if (stops.length === 1) {
      map.setCenter({ lat: stops[0].lat, lng: stops[0].lng });
      map.setZoom(14);
    } else {
      map.fitBounds(bounds, 80);
    }
  }, [stops, legs, directionSteps]);

  // Transit overlay — PDF-sourced rail/bus/bike/scooter/drop-off markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    transitMarkersRef.current.forEach((m) => m.setMap(null));
    transitMarkersRef.current = [];
    VENUE_TRANSIT.forEach((point) => {
      if (!layerVisibility[point.type]) return;
      const marker = new window.google.maps.Marker({
        position: { lat: point.lat, lng: point.lng },
        map,
        icon: makeTransitIcon(point.type),
        title: point.name,
        zIndex: 12,
        optimized: false,
      });
      marker.addListener('click', () => {
        clickWindowRef.current?.setContent(transitInfoHtml(point));
        clickWindowRef.current?.open(map, marker);
      });
      transitMarkersRef.current.push(marker);
    });
    return () => {
      transitMarkersRef.current.forEach((m) => m.setMap(null));
      transitMarkersRef.current = [];
    };
  }, [mapReady, layerVisibility]);

  const hasRoutes = legs.length > 0;
  const summaryLine = [
    `${legs.length} leg${legs.length !== 1 ? 's' : ''}`,
    totalDuration > 0 ? formatDuration(totalDuration) : '',
    totalDistance > 0 ? formatDistance(totalDistance) : '',
  ].filter(Boolean).join(' · ');

  return (
    <View style={styles.wrapper}>
      {/* Google Maps container */}
      <div
        ref={containerRef as React.RefObject<HTMLDivElement>}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 56 }}
      />

      {/* Legend + Layer Toggles */}
      {!mapError && (
        <div style={{ ...LEGEND_STYLE, bottom: hasRoutes ? 116 : 68 }}>
          {hasRoutes && (
            <>
              <div style={LEGEND_ROW}>
                <div style={{ ...LEGEND_SWATCH, borderTop: `3px dashed ${colors.primary}` }} />
                <span style={LEGEND_LABEL}>Walk</span>
              </div>
              <div style={LEGEND_ROW}>
                <div style={{ ...LEGEND_SWATCH, borderTop: `4px solid ${colors.secondary}` }} />
                <span style={LEGEND_LABEL}>Transit</span>
              </div>
              <div style={LEGEND_ROW}>
                <div style={LEGEND_DOT}><span style={LEGEND_NUM}>1</span></div>
                <span style={LEGEND_LABEL}>Venue</span>
              </div>
              {!hasSteps && (
                <div style={{ ...LEGEND_LABEL, marginTop: 5, color: '#aaa', fontSize: 10, maxWidth: 110, lineHeight: '1.3' }}>
                  Tap Routes → Get Directions for step detail
                </div>
              )}
              <div style={{ borderTop: '1px solid #E5E7EB', marginTop: 4, marginBottom: 4 }} />
            </>
          )}
          <div style={{ ...LEGEND_LABEL, fontSize: 9, color: '#9CA3AF', letterSpacing: '0.06em', marginBottom: 4 }}>
            NEARBY
          </div>
          {(Object.keys(TRANSIT_LAYER_CONFIG) as TransitLayer[]).map((layer) => {
            const { label, fill, displayName } = TRANSIT_LAYER_CONFIG[layer];
            const active = layerVisibility[layer];
            return (
              <div
                key={layer}
                onClick={() => setLayerVisibility((prev) => ({ ...prev, [layer]: !prev[layer] }))}
                style={{ ...LEGEND_ROW, cursor: 'pointer', opacity: active ? 1 : 0.4 }}
              >
                <div style={{
                  width: 18, height: 18, borderRadius: '50%',
                  background: active ? fill : '#9CA3AF',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <span style={{ fontSize: 9, color: '#fff', fontWeight: 700, fontFamily: 'system-ui,sans-serif' }}>
                    {label}
                  </span>
                </div>
                <span style={{ ...LEGEND_LABEL, fontSize: 11, color: active ? '#374151' : '#9CA3AF' }}>
                  {displayName}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Directions sheet */}
      {!mapError && hasRoutes && (
        <div style={{ position: 'absolute', bottom: 56, left: 0, right: 0, zIndex: 10 }}>
          {/* Sheet content */}
          {sheetOpen && (
            <div style={SHEET_CONTENT_STYLE}>
              {stops.slice(0, -1).map((from, i) => {
                const to = stops[i + 1];
                const stepKey = `${from.id}-${to.id}`;
                const steps = directionSteps[stepKey] ?? [];
                const leg = legs.find(
                  (l) => l.from_stop_id === from.id && l.to_stop_id === to.id,
                );
                return (
                  <div key={stepKey} style={{ marginBottom: i < stops.length - 2 ? 14 : 0 }}>
                    {/* Leg header */}
                    <div style={SHEET_LEG_HEADER}>
                      <span style={{ fontWeight: 700, fontSize: 12, color: '#1F2937' }}>
                        {i + 1}. {from.name}
                      </span>
                      <span style={{ color: '#9CA3AF', fontSize: 12 }}>→</span>
                      <span style={{ fontWeight: 700, fontSize: 12, color: '#1F2937', flex: 1 }}>
                        {to.name}
                      </span>
                      {leg && (
                        <span style={{ fontSize: 11, color: '#6B7280', whiteSpace: 'nowrap' }}>
                          {formatDuration(leg.duration_s ?? 0)} · {formatDistance(leg.distance_m ?? 0)}
                        </span>
                      )}
                    </div>
                    {steps.length > 0 ? (
                      <div style={{ paddingLeft: 8 }}>
                        {steps.map((step, j) => (
                          <SheetStepRow key={j} step={step} />
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: 11, color: '#9CA3AF', paddingLeft: 8, marginTop: 4 }}>
                        Tap <b>Routes</b> → <b>Get Directions</b> to see step detail
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Handle bar */}
          <div
            style={SHEET_HANDLE_STYLE}
            onClick={() => setSheetOpen((o) => !o)}
            role="button"
            aria-label={sheetOpen ? 'Collapse directions' : 'Expand directions'}
          >
            <span style={{ fontSize: 12, fontWeight: 600, color: '#1F2937', fontFamily: 'system-ui,sans-serif' }}>
              {summaryLine}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 11, color: colors.primary, fontWeight: 600, fontFamily: 'system-ui,sans-serif' }}>
                {sheetOpen ? 'Hide' : 'Details'}
              </span>
              <span style={{ fontSize: 14, color: colors.primary }}>{sheetOpen ? '▼' : '▲'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {mapError && (
        <View style={styles.overlay}>
          <Feather name="alert-circle" size={32} color={colors.destructive} />
          <Text style={styles.errorText}>{mapError}</Text>
        </View>
      )}

      {/* Empty state */}
      {!mapError && stops.length === 0 && (
        <View style={styles.overlay}>
          <Feather name="map-pin" size={48} color={colors.muted} />
          <Text style={styles.emptyTitle}>No venues yet</Text>
          <Text style={styles.emptyHint}>Add venues in the Builder tab to see them on the map</Text>
          <Pressable
            onPress={() => router.push('/')}
            accessibilityRole="button"
            style={({ pressed }) => [styles.goBtn, pressed && { opacity: 0.8 }]}
          >
            <Text style={styles.goBtnText}>Go to Builder</Text>
          </Pressable>
        </View>
      )}

      {/* Info bar */}
      <View style={styles.infoBar}>
        <Text style={styles.infoText}>
          {stops.length} {stops.length === 1 ? 'venue' : 'venues'}
          {legs.length > 0 ? `  ·  ${legs.length} ${legs.length === 1 ? 'route' : 'routes'}` : ''}
          {hasSteps ? '  ·  step view' : ''}
        </Text>
        {stops.length >= 2 && (
          <Pressable
            onPress={() => router.push('/routes')}
            accessibilityRole="button"
            style={({ pressed }) => [styles.routesBtn, pressed && { opacity: 0.65 }]}
          >
            <Text style={styles.routesBtnText}>Routes</Text>
            <Feather name="arrow-right" size={14} color={colors.primary} />
          </Pressable>
        )}
      </View>
    </View>
  );
}

// ── Legend inline styles ───────────────────────────────────────────────────────

const LEGEND_STYLE: React.CSSProperties = {
  position: 'absolute', bottom: 116, left: 12,
  background: 'rgba(255,255,255,0.95)',
  backdropFilter: 'blur(4px)',
  borderRadius: 10, padding: '10px 12px',
  boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
  display: 'flex', flexDirection: 'column', gap: 7, zIndex: 10,
};
const LEGEND_ROW: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 8 };
const LEGEND_SWATCH: React.CSSProperties = { width: 28, flexShrink: 0 };
const LEGEND_LABEL: React.CSSProperties = {
  fontFamily: 'system-ui, sans-serif', fontSize: 12, color: '#374151', fontWeight: '500',
};
const LEGEND_DOT: React.CSSProperties = {
  width: 20, height: 20, borderRadius: '50%', background: colors.primary,
  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
};
const LEGEND_NUM: React.CSSProperties = {
  color: '#fff', fontSize: 10, fontWeight: '700', fontFamily: 'system-ui, sans-serif',
};

// ── Directions sheet inline styles ────────────────────────────────────────────

const SHEET_HANDLE_STYLE: React.CSSProperties = {
  height: 48, display: 'flex', alignItems: 'center',
  justifyContent: 'space-between', padding: '0 16px',
  background: 'rgba(240,245,255,0.97)', backdropFilter: 'blur(8px)',
  borderTop: `1px solid #C0CFF5`, cursor: 'pointer',
  userSelect: 'none',
};
const SHEET_CONTENT_STYLE: React.CSSProperties = {
  maxHeight: 300, overflowY: 'auto',
  background: 'rgba(240,245,255,0.97)', backdropFilter: 'blur(8px)',
  padding: '12px 16px', borderTop: `1px solid #C0CFF5`,
};
const SHEET_LEG_HEADER: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  marginBottom: 8, flexWrap: 'wrap',
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
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 56,
    alignItems: 'center', justifyContent: 'center',
    gap: spacing.md, paddingHorizontal: spacing.xl,
    backgroundColor: colors.background,
  },
  emptyTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 24, color: colors.muted },
  emptyHint: {
    fontFamily: 'Barlow_400Regular', fontSize: 15, color: colors.muted,
    textAlign: 'center', lineHeight: 22,
  },
  goBtn: {
    backgroundColor: colors.primary, borderRadius: radius.md,
    paddingHorizontal: spacing.xl, paddingVertical: spacing.md,
    minHeight: 48, alignItems: 'center', justifyContent: 'center',
  },
  goBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 15, color: colors.onPrimary },
  errorText: {
    fontFamily: 'Barlow_400Regular', fontSize: 14,
    color: colors.destructive, textAlign: 'center', lineHeight: 20,
  },
  infoBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0, height: 56,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: colors.surface, paddingHorizontal: spacing.md,
    borderTopWidth: 1, borderTopColor: colors.border,
  },
  infoText: { fontFamily: 'Barlow_500Medium', fontSize: 14, color: colors.foreground },
  routesBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingVertical: 6, paddingHorizontal: spacing.sm, minHeight: 44,
  },
  routesBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 14, color: colors.primary },
});
