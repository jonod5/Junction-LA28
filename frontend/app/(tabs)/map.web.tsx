import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';
import { decodePolyline } from '@/lib/polyline';
import { useTrip } from '@/lib/store';

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

function toLatLng(encoded: string) {
  return decodePolyline(encoded).map((p) => ({ lat: p.latitude, lng: p.longitude }));
}

/** SVG pill badge for transit line labels */
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

/** Walking dashed-line icon pattern */
const WALK_DASH = {
  path: 'M 0,-1 0,1',
  strokeOpacity: 0.85,
  strokeColor: colors.primary,
  scale: 3,
};

export default function MapWebScreen() {
  const { trip, directionSteps } = useTrip();
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const infoWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [hasSteps, setHasSteps] = useState(false);

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const legs = trip?.legs ?? [];

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
        infoWindowRef.current = new window.google.maps.InfoWindow();
      })
      .catch((e) => setMapError(e.message));
    return () => { cancelled = true; };
  }, []);

  // Sync markers + step polylines whenever trip or directionSteps change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps) return;

    // Clear existing
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];

    if (stops.length === 0) return;

    const bounds = new window.google.maps.LatLngBounds();

    // ── Venue markers ────────────────────────────────────────────────────────
    stops.forEach((s, i) => {
      const label = String(i + 1);
      const marker = new window.google.maps.Marker({
        position: { lat: s.lat, lng: s.lng },
        map,
        zIndex: 20,
        label: { text: label, color: '#fff', fontWeight: '700', fontSize: '13px' },
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
        infoWindowRef.current?.setContent(
          `<div style="font-family:system-ui,sans-serif;padding:4px 2px">
            <b style="font-size:13px">${i + 1}. ${s.name}</b>
          </div>`,
        );
        infoWindowRef.current?.open(map, marker);
      });
      markersRef.current.push(marker);
      bounds.extend({ lat: s.lat, lng: s.lng });
    });

    // ── Route segments ───────────────────────────────────────────────────────
    const stepKeys = Object.keys(directionSteps);
    const usingSteps = stepKeys.length > 0;
    setHasSteps(usingSteps);

    if (usingSteps) {
      // Step-level rendering: walking dashed + transit colored with badge
      stepKeys.forEach((legKey) => {
        const steps = directionSteps[legKey];
        steps.forEach((step) => {
          if (!step.polyline) return;
          const path = toLatLng(step.polyline);
          if (path.length === 0) return;

          if (step.mode === 'walking') {
            // Dashed orange line
            const poly = new window.google.maps.Polyline({
              path,
              geodesic: true,
              strokeOpacity: 0,
              strokeWeight: 3,
              icons: [{ icon: WALK_DASH, offset: '0', repeat: '12px' }],
              map,
              zIndex: 5,
            });
            polylinesRef.current.push(poly);

          } else if (step.mode === 'transit') {
            const lineColor = step.transit_color || colors.secondary;

            // Solid transit line with white outline for readability
            const outline = new window.google.maps.Polyline({
              path, geodesic: true,
              strokeColor: '#fff', strokeOpacity: 0.6, strokeWeight: 9,
              map, zIndex: 8,
            });
            const poly = new window.google.maps.Polyline({
              path, geodesic: true,
              strokeColor: lineColor, strokeOpacity: 1, strokeWeight: 6,
              map, zIndex: 9,
            });
            polylinesRef.current.push(outline, poly);

            // InfoWindow on click
            const openInfo = (pos: google.maps.LatLng | null | undefined) => {
              const content = `
                <div style="font-family:system-ui,sans-serif;max-width:220px;line-height:1.4">
                  <div style="background:${lineColor};color:#fff;padding:4px 10px;border-radius:12px;display:inline-block;font-weight:700;font-size:12px;margin-bottom:6px">
                    ${step.transit_line_short ?? step.transit_line ?? 'Transit'}
                  </div>
                  <div style="font-weight:600;font-size:13px">${step.transit_line ?? ''}${step.headsign ? ` → ${step.headsign}` : ''}</div>
                  ${step.departure_stop ? `<div style="font-size:12px;color:#555;margin-top:4px">Board: <b>${step.departure_stop}</b></div>` : ''}
                  ${step.arrival_stop ? `<div style="font-size:12px;color:#555">Exit: <b>${step.arrival_stop}</b></div>` : ''}
                  ${step.num_stops != null ? `<div style="font-size:11px;color:#888;margin-top:2px">${step.num_stops} stop${step.num_stops !== 1 ? 's' : ''}</div>` : ''}
                </div>`;
              infoWindowRef.current?.setContent(content);
              infoWindowRef.current?.setPosition(pos ?? path[Math.floor(path.length / 2)]);
              infoWindowRef.current?.open(map);
            };
            poly.addListener('click', (e: google.maps.MapMouseEvent) => openInfo(e.latLng));

            // Badge at midpoint of the step
            const label = step.transit_line_short ?? (step.transit_line?.slice(0, 8) ?? '');
            if (label) {
              const mid = path[Math.floor(path.length / 2)];
              const badge = new window.google.maps.Marker({
                position: mid,
                map,
                icon: makeBadgeIcon(label, lineColor),
                title: step.transit_line ?? '',
                zIndex: 15,
                optimized: false,
              });
              badge.addListener('click', () => openInfo(badge.getPosition()));
              markersRef.current.push(badge);
            }

          } else {
            // Driving or other — gray dashed
            const poly = new window.google.maps.Polyline({
              path, geodesic: true,
              strokeColor: '#9CA3AF', strokeOpacity: 0.7, strokeWeight: 4,
              map, zIndex: 5,
            });
            polylinesRef.current.push(poly);
          }
        });
      });

    } else {
      // Fallback: overview polyline per leg, color by mode
      legs.forEach((leg) => {
        if (!leg.polyline) return;
        const path = toLatLng(leg.polyline);
        const isWalk = leg.mode === 'walking';
        const isTransit = leg.mode === 'transit';

        if (isWalk) {
          const poly = new window.google.maps.Polyline({
            path, geodesic: true,
            strokeOpacity: 0, strokeWeight: 3,
            icons: [{ icon: WALK_DASH, offset: '0', repeat: '12px' }],
            map, zIndex: 5,
          });
          polylinesRef.current.push(poly);
        } else {
          const color = isTransit ? colors.secondary : '#9CA3AF';
          const outline = new window.google.maps.Polyline({
            path, geodesic: true,
            strokeColor: '#fff', strokeOpacity: 0.6, strokeWeight: 9,
            map, zIndex: 8,
          });
          const poly = new window.google.maps.Polyline({
            path, geodesic: true,
            strokeColor: color, strokeOpacity: 0.95, strokeWeight: 6,
            map, zIndex: 9,
          });
          polylinesRef.current.push(outline, poly);
        }
      });
    }

    // Fit map to stops
    if (stops.length === 1) {
      map.setCenter({ lat: stops[0].lat, lng: stops[0].lng });
      map.setZoom(14);
    } else {
      map.fitBounds(bounds, 80);
    }
  }, [stops, legs, directionSteps]);

  const hasRoutes = legs.length > 0;

  return (
    <View style={styles.wrapper}>
      {/* Google Maps container */}
      <div
        ref={containerRef as React.RefObject<HTMLDivElement>}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 56 }}
      />

      {/* Legend — only show when routes exist */}
      {!mapError && hasRoutes && (
        <div style={LEGEND_STYLE}>
          <div style={LEGEND_ROW}>
            <div style={{ ...LEGEND_LINE, borderTop: `3px dashed ${colors.primary}` }} />
            <span style={LEGEND_LABEL}>Walk</span>
          </div>
          <div style={LEGEND_ROW}>
            <div style={{ ...LEGEND_LINE, borderTop: `4px solid ${colors.secondary}` }} />
            <span style={LEGEND_LABEL}>Transit</span>
          </div>
          <div style={LEGEND_ROW}>
            <div style={LEGEND_DOT}><span style={LEGEND_NUM}>1</span></div>
            <span style={LEGEND_LABEL}>Venue</span>
          </div>
          {!hasSteps && (
            <div style={{ ...LEGEND_LABEL, marginTop: 6, color: '#999', fontSize: 10, maxWidth: 100 }}>
              Get directions in Routes tab for detail view
            </div>
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

      {/* Empty state overlay */}
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

// ── Legend styles (plain JS objects for HTML div) ─────────────────────────────

const LEGEND_STYLE: React.CSSProperties = {
  position: 'absolute',
  bottom: 68,
  left: 12,
  background: 'rgba(255,255,255,0.95)',
  backdropFilter: 'blur(4px)',
  borderRadius: 10,
  padding: '10px 12px',
  boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
  display: 'flex',
  flexDirection: 'column',
  gap: 7,
  zIndex: 10,
};

const LEGEND_ROW: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

const LEGEND_LINE: React.CSSProperties = {
  width: 28,
  flexShrink: 0,
};

const LEGEND_LABEL: React.CSSProperties = {
  fontFamily: 'system-ui, sans-serif',
  fontSize: 12,
  color: '#374151',
  fontWeight: '500',
};

const LEGEND_DOT: React.CSSProperties = {
  width: 20,
  height: 20,
  borderRadius: '50%',
  background: colors.primary,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
};

const LEGEND_NUM: React.CSSProperties = {
  color: '#fff',
  fontSize: 10,
  fontWeight: '700',
  fontFamily: 'system-ui, sans-serif',
};

// ── Subtle map style — de-emphasize roads so routes stand out ─────────────────
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
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 56,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    backgroundColor: colors.background,
  },
  emptyTitle: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 24,
    color: colors.muted,
  },
  emptyHint: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 15,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 22,
  },
  goBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  goBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.onPrimary,
  },
  errorText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 14,
    color: colors.destructive,
    textAlign: 'center',
    lineHeight: 20,
  },
  infoBar: {
    position: 'absolute',
    bottom: 0, left: 0, right: 0,
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  infoText: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 14,
    color: colors.foreground,
  },
  routesBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    minHeight: 44,
  },
  routesBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 14,
    color: colors.primary,
  },
});
