import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
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

export default function MapWebScreen() {
  const { trip } = useTrip();
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const [mapError, setMapError] = useState<string | null>(null);

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
        });
        mapRef.current = map;
      })
      .catch((e) => setMapError(e.message));
    return () => { cancelled = true; };
  }, []);

  // Sync markers + polylines on trip change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps) return;

    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];

    if (stops.length === 0) return;

    const bounds = new window.google.maps.LatLngBounds();

    stops.forEach((s, i) => {
      const label = String(i + 1);
      const marker = new window.google.maps.Marker({
        position: { lat: s.lat, lng: s.lng },
        map,
        label: { text: label, color: '#fff', fontWeight: '700', fontSize: '13px' },
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          fillColor: colors.primary,
          fillOpacity: 1,
          strokeColor: '#fff',
          strokeWeight: 2,
          scale: 14,
        },
        title: s.name,
      });
      const info = new window.google.maps.InfoWindow({ content: `<b>${s.name}</b>` });
      marker.addListener('click', () => info.open(map, marker));
      markersRef.current.push(marker);
      bounds.extend({ lat: s.lat, lng: s.lng });
    });

    legs.forEach((leg) => {
      if (!leg.polyline) return;
      const path = decodePolyline(leg.polyline).map((p) => ({
        lat: p.latitude,
        lng: p.longitude,
      }));
      const poly = new window.google.maps.Polyline({
        path,
        geodesic: true,
        strokeColor: colors.secondary,
        strokeOpacity: 0.9,
        strokeWeight: 4,
        map,
      });
      polylinesRef.current.push(poly);
    });

    if (stops.length === 1) {
      map.setCenter({ lat: stops[0].lat, lng: stops[0].lng });
      map.setZoom(14);
    } else {
      map.fitBounds(bounds, 60);
    }
  }, [stops, legs]);

  return (
    <View style={styles.wrapper}>
      {/* Google Maps container — absolute fill so it has real pixel dimensions */}
      <div
        ref={containerRef as React.RefObject<HTMLDivElement>}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 56 }}
      />

      {/* Error overlay */}
      {mapError && (
        <View style={styles.errorOverlay}>
          <Feather name="alert-circle" size={32} color={colors.destructive} />
          <Text style={styles.errorText}>{mapError}</Text>
        </View>
      )}

      {/* Empty state overlay */}
      {!mapError && stops.length === 0 && (
        <View style={styles.emptyOverlay}>
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

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: colors.background },
  emptyOverlay: {
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
  errorOverlay: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 56,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    backgroundColor: colors.background,
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
