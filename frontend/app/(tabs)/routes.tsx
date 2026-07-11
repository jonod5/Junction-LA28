import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { ModeSelector, TravelMode } from '@/components/ModeSelector';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { api, Leg } from '@/lib/api';
import { formatDistance, formatDuration } from '@/lib/polyline';
import { useTrip } from '@/lib/store';

interface LegState {
  mode: TravelMode;
  loading: boolean;
  error: string | null;
}

export default function RoutesScreen() {
  const { trip, saveLeg } = useTrip();
  const router = useRouter();

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const legs = trip?.legs ?? [];

  // Per-pair mode + loading state, keyed by "fromId-toId"
  const [legStates, setLegStates] = useState<Record<string, LegState>>({});

  const key = (fromId: number, toId: number) => `${fromId}-${toId}`;

  const getLegState = (fromId: number, toId: number): LegState =>
    legStates[key(fromId, toId)] ?? { mode: 'transit', loading: false, error: null };

  const setMode = (fromId: number, toId: number, mode: TravelMode) => {
    setLegStates((prev) => ({
      ...prev,
      [key(fromId, toId)]: { ...getLegState(fromId, toId), mode, error: null },
    }));
  };

  const fetchDirections = async (fromStop: { id: number; lat: number; lng: number; name: string }, toStop: { id: number; lat: number; lng: number; name: string }) => {
    const k = key(fromStop.id, toStop.id);
    const state = getLegState(fromStop.id, toStop.id);
    setLegStates((prev) => ({ ...prev, [k]: { ...state, loading: true, error: null } }));

    try {
      const result = await api.getDirections(
        `${fromStop.lat},${fromStop.lng}`,
        `${toStop.lat},${toStop.lng}`,
        state.mode,
      );
      if (!trip) return;
      const leg = await api.upsertLeg(trip.id, {
        from_stop_id: fromStop.id,
        to_stop_id: toStop.id,
        mode: result.mode,
        distance_m: result.distance_m,
        duration_s: result.duration_s,
        polyline: result.polyline,
      });
      saveLeg(leg);
      setLegStates((prev) => ({ ...prev, [k]: { ...state, loading: false, error: null } }));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not get directions';
      setLegStates((prev) => ({ ...prev, [k]: { ...state, loading: false, error: msg } }));
    }
  };

  const existingLeg = (fromId: number, toId: number, mode: string): Leg | undefined =>
    legs.find(
      (l) => l.from_stop_id === fromId && l.to_stop_id === toId && l.mode === mode,
    );

  const totalDuration = legs.reduce((sum, l) => sum + (l.duration_s ?? 0), 0);
  const totalDistance = legs.reduce((sum, l) => sum + (l.distance_m ?? 0), 0);

  if (!trip || stops.length < 2) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.emptyContainer}>
          <Feather name="navigation" size={48} color={colors.muted} />
          <Text style={styles.emptyTitle}>No routes yet</Text>
          <Text style={styles.emptyHint}>Add at least 2 venues in the Builder tab</Text>
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

  const pairs = stops.slice(0, -1).map((from, i) => ({ from, to: stops[i + 1] }));

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Total summary */}
        {legs.length > 0 && (
          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Total journey</Text>
            <View style={styles.summaryRow}>
              <View style={styles.summaryItem}>
                <Feather name="clock" size={14} color={colors.secondary} />
                <Text style={styles.summaryValue}>{formatDuration(totalDuration)}</Text>
              </View>
              <View style={styles.summarySep} />
              <View style={styles.summaryItem}>
                <Feather name="map-pin" size={14} color={colors.secondary} />
                <Text style={styles.summaryValue}>{formatDistance(totalDistance)}</Text>
              </View>
              <Pressable
                onPress={() => router.push('/comparison')}
                accessibilityRole="button"
                accessibilityLabel="Compare all travel modes"
                style={({ pressed }) => [styles.compareBtn, pressed && styles.compareBtnPressed]}
              >
                <Text style={styles.compareBtnText}>Compare modes</Text>
                <Feather name="bar-chart-2" size={13} color={colors.primary} />
              </Pressable>
            </View>
          </View>
        )}

        {/* Per-leg cards */}
        {pairs.map(({ from, to }) => {
          const k = key(from.id, to.id);
          const state = getLegState(from.id, to.id);
          const leg = existingLeg(from.id, to.id, state.mode);
          const isDriving = state.mode === 'driving';

          return (
            <View key={k} style={styles.legCard}>
              {/* From → To */}
              <View style={styles.legHeader}>
                <View style={styles.legEndpoint}>
                  <View style={[styles.dot, styles.dotFrom]} />
                  <Text style={styles.endpointName} numberOfLines={1}>
                    {from.name}
                  </Text>
                </View>
                <Feather name="arrow-down" size={14} color={colors.muted} style={styles.arrow} />
                <View style={styles.legEndpoint}>
                  <View style={[styles.dot, styles.dotTo]} />
                  <Text style={styles.endpointName} numberOfLines={1}>
                    {to.name}
                  </Text>
                </View>
              </View>

              {/* Mode selector */}
              <ModeSelector value={state.mode} onChange={(m) => setMode(from.id, to.id, m)} />

              {/* Driving warning */}
              {isDriving && (
                <View style={styles.drivingWarn}>
                  <Feather name="alert-triangle" size={13} color={colors.drivingWarning} />
                  <Text style={styles.drivingWarnText}>
                    Venue parking closed to spectators during LA28 Games
                  </Text>
                </View>
              )}

              {/* Result or CTA */}
              {leg ? (
                <View style={styles.legResult}>
                  <View style={styles.legResultBadge}>
                    <Feather name="clock" size={13} color={colors.secondary} />
                    <Text style={styles.legResultText}>{formatDuration(leg.duration_s ?? 0)}</Text>
                  </View>
                  <View style={styles.legResultBadge}>
                    <Feather name="map-pin" size={13} color={colors.secondary} />
                    <Text style={styles.legResultText}>{formatDistance(leg.distance_m ?? 0)}</Text>
                  </View>
                  <Pressable
                    onPress={() => fetchDirections(from, to)}
                    disabled={state.loading}
                    accessibilityRole="button"
                    accessibilityLabel="Refresh directions"
                    style={({ pressed }) => [styles.refreshBtn, pressed && { opacity: 0.65 }]}
                  >
                    <Feather name="refresh-cw" size={14} color={colors.muted} />
                  </Pressable>
                </View>
              ) : (
                <Pressable
                  onPress={() => fetchDirections(from, to)}
                  disabled={state.loading}
                  accessibilityRole="button"
                  accessibilityLabel={`Get ${state.mode} directions from ${from.name} to ${to.name}`}
                  style={({ pressed }) => [
                    styles.directionsBtn,
                    state.loading && styles.directionsBtnDisabled,
                    pressed && styles.directionsBtnPressed,
                  ]}
                >
                  {state.loading ? (
                    <ActivityIndicator color={colors.onPrimary} size="small" />
                  ) : (
                    <>
                      <Feather name="navigation" size={15} color={colors.onPrimary} />
                      <Text style={styles.directionsBtnText}>Get Directions</Text>
                    </>
                  )}
                </Pressable>
              )}

              {state.error && (
                <Text style={styles.legError} accessibilityRole="alert">
                  {state.error}
                </Text>
              )}
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
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
  goBtnPressed: { opacity: 0.8 },
  goBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.onPrimary,
  },
  // ── Summary card ──────────────────────────────────────────────────────────
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadow.sm,
  },
  summaryLabel: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 12,
    color: colors.muted,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  summaryItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  summaryValue: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 20,
    color: colors.foreground,
  },
  summarySep: {
    width: 1,
    height: 16,
    backgroundColor: colors.border,
  },
  compareBtn: {
    marginLeft: 'auto',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    minHeight: 44,
  },
  compareBtnPressed: { opacity: 0.65 },
  compareBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 13,
    color: colors.primary,
  },
  // ── Leg card ──────────────────────────────────────────────────────────────
  legCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md,
    ...shadow.sm,
  },
  legHeader: {
    gap: spacing.xs,
  },
  legEndpoint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    flexShrink: 0,
  },
  dotFrom: { backgroundColor: colors.primary },
  dotTo: { backgroundColor: colors.secondary },
  arrow: {
    marginLeft: 10,
  },
  endpointName: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 14,
    color: colors.foreground,
    flex: 1,
  },
  drivingWarn: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    backgroundColor: '#FEF2F2',
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  drivingWarnText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 12,
    color: colors.drivingWarning,
    flex: 1,
    lineHeight: 16,
  },
  legResult: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  legResultBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.mutedBg,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  legResultText: {
    fontFamily: 'BarlowCondensed_600SemiBold',
    fontSize: 16,
    color: colors.foreground,
  },
  refreshBtn: {
    marginLeft: 'auto',
    padding: spacing.sm,
    minHeight: 44,
    minWidth: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  directionsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.secondary,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    minHeight: 48,
  },
  directionsBtnDisabled: { opacity: 0.5 },
  directionsBtnPressed: { opacity: 0.8, transform: [{ scale: 0.98 }] },
  directionsBtnText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.onPrimary,
  },
  legError: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.destructive,
    textAlign: 'center',
  },
});
