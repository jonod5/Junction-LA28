import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useEffect, useRef } from 'react';
import { Platform, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';
import { useTrip } from '@/lib/store';
import { decodePolyline } from '@/lib/polyline';

// react-native-maps only works on native (iOS/Android)
const MapView =
  Platform.OS !== 'web' ? require('react-native-maps').default : null;
const { Marker, Polyline } =
  Platform.OS !== 'web' ? require('react-native-maps') : { Marker: null, Polyline: null };

export default function MapScreen() {
  const { trip } = useTrip();
  const router = useRouter();
  const mapRef = useRef<any>(null);

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const legs = trip?.legs ?? [];

  useEffect(() => {
    if (!mapRef.current || stops.length === 0 || Platform.OS === 'web') return;
    const coords = stops.map((s) => ({ latitude: s.lat, longitude: s.lng }));
    mapRef.current.fitToCoordinates(coords, {
      edgePadding: { top: 60, right: 60, bottom: 120, left: 60 },
      animated: true,
    });
  }, [stops]);

  // ── Web fallback ───────────────────────────────────────────────────────────
  if (Platform.OS === 'web') {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.webFallback}>
          <Feather name="smartphone" size={48} color={colors.muted} />
          <Text style={styles.webFallbackTitle}>Map View</Text>
          <Text style={styles.webFallbackText}>
            Interactive map is available in the iOS and Android apps.
          </Text>
          {stops.length > 0 && (
            <View style={styles.stopsList}>
              {stops.map((s, i) => (
                <View key={s.id} style={styles.stopsListRow}>
                  <View style={styles.stopNumBadge}>
                    <Text style={styles.stopNumText}>{i + 1}</Text>
                  </View>
                  <Text style={styles.stopsListName}>{s.name}</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      </SafeAreaView>
    );
  }

  // ── No trip / no stops ────────────────────────────────────────────────────
  if (!trip || stops.length === 0) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.emptyContainer}>
          <Feather name="map" size={48} color={colors.muted} />
          <Text style={styles.emptyTitle}>No venues yet</Text>
          <Text style={styles.emptyHint}>Add venues in the Builder tab to see them on the map</Text>
          <Pressable
            onPress={() => router.push('/')}
            accessibilityRole="button"
            style={({ pressed }) => [styles.goBtn, pressed && styles.goBtnPressed]}
          >
            <Text style={styles.goBtnText}>Go to Builder</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.screen}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        initialRegion={{
          latitude: 34.052,
          longitude: -118.243,
          latitudeDelta: 0.35,
          longitudeDelta: 0.35,
        }}
      >
        {/* Venue markers */}
        {stops.map((s, i) => (
          <Marker
            key={s.id}
            coordinate={{ latitude: s.lat, longitude: s.lng }}
            title={s.name}
            pinColor={colors.primary}
            accessibilityLabel={`Stop ${i + 1}: ${s.name}`}
          />
        ))}

        {/* Route polylines */}
        {legs.map((leg) => {
          if (!leg.polyline) return null;
          const coords = decodePolyline(leg.polyline);
          return (
            <Polyline
              key={leg.id}
              coordinates={coords}
              strokeColor={colors.secondary}
              strokeWidth={3}
            />
          );
        })}
      </MapView>

      {/* Floating info bar */}
      <SafeAreaView style={styles.infoBarWrap} pointerEvents="box-none">
        <View style={styles.infoBar}>
          <Text style={styles.infoText}>
            {stops.length} {stops.length === 1 ? 'venue' : 'venues'}
            {legs.length > 0 ? `  ·  ${legs.length} ${legs.length === 1 ? 'route' : 'routes'}` : ''}
          </Text>
          {stops.length >= 2 && (
            <Pressable
              onPress={() => router.push('/routes')}
              accessibilityRole="button"
              accessibilityLabel="View routes"
              style={({ pressed }) => [styles.routesBtn, pressed && styles.routesBtnPressed]}
            >
              <Text style={styles.routesBtnText}>Routes</Text>
              <Feather name="arrow-right" size={14} color={colors.primary} />
            </Pressable>
          )}
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  // ── Web fallback ───────────────────────────────────────────────────────────
  webFallback: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    gap: spacing.md,
  },
  webFallbackTitle: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 24,
    color: colors.foreground,
  },
  webFallbackText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 15,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 22,
  },
  stopsList: {
    width: '100%',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  stopsListRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadow.sm,
  },
  stopNumBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stopNumText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 13,
    color: colors.onPrimary,
  },
  stopsListName: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.foreground,
  },
  // ── Empty ─────────────────────────────────────────────────────────────────
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
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
  goBtnPressed: {
    opacity: 0.8,
  },
  goBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.onPrimary,
  },
  // ── Floating bar ──────────────────────────────────────────────────────────
  infoBarWrap: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
  },
  infoBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    marginHorizontal: spacing.md,
    marginBottom: spacing.lg,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    ...shadow.md,
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
  routesBtnPressed: {
    opacity: 0.65,
  },
  routesBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 14,
    color: colors.primary,
  },
});
