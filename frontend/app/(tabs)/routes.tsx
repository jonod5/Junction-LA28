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
import { api, DirectionStep, DirectionsResult, Leg } from '@/lib/api';
import { formatDistance, formatDuration } from '@/lib/polyline';
import { useTrip } from '@/lib/store';

interface LegState {
  mode: TravelMode;
  loading: boolean;
  error: string | null;
  result: DirectionsResult | null;
  stepsOpen: boolean;
}

const VEHICLE_ICONS: Record<string, React.ComponentProps<typeof Feather>['name']> = {
  subway: 'navigation',
  bus: 'navigation',
  tram: 'navigation',
  rail: 'navigation',
  ferry: 'anchor',
  default: 'navigation',
};

export default function RoutesScreen() {
  const { trip, saveLeg, saveDirectionSteps } = useTrip();
  const router = useRouter();

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const legs = trip?.legs ?? [];

  const [legStates, setLegStates] = useState<Record<string, LegState>>({});

  const key = (fromId: number, toId: number) => `${fromId}-${toId}`;

  const getLegState = (fromId: number, toId: number): LegState =>
    legStates[key(fromId, toId)] ?? {
      mode: 'transit',
      loading: false,
      error: null,
      result: null,
      stepsOpen: false,
    };

  const patch = (fromId: number, toId: number, update: Partial<LegState>) =>
    setLegStates((prev) => ({
      ...prev,
      [key(fromId, toId)]: { ...getLegState(fromId, toId), ...update },
    }));

  const fetchDirections = async (
    fromStop: { id: number; lat: number; lng: number; name: string },
    toStop: { id: number; lat: number; lng: number; name: string },
  ) => {
    const state = getLegState(fromStop.id, toStop.id);
    patch(fromStop.id, toStop.id, { loading: true, error: null });

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
      saveDirectionSteps(fromStop.id, toStop.id, result.steps);
      patch(fromStop.id, toStop.id, { loading: false, result, stepsOpen: true });
    } catch (e: unknown) {
      patch(fromStop.id, toStop.id, {
        loading: false,
        error: e instanceof Error ? e.message : 'Could not get directions',
      });
    }
  };

  const savedLeg = (fromId: number, toId: number, mode: string): Leg | undefined =>
    legs.find((l) => l.from_stop_id === fromId && l.to_stop_id === toId && l.mode === mode);

  const totalDuration = legs.reduce((s, l) => s + (l.duration_s ?? 0), 0);
  const totalDistance = legs.reduce((s, l) => s + (l.distance_m ?? 0), 0);

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
            style={({ pressed }) => [styles.goBtn, pressed && { opacity: 0.8 }]}
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
              <StatBadge icon="clock" value={formatDuration(totalDuration)} />
              <View style={styles.summarySep} />
              <StatBadge icon="map-pin" value={formatDistance(totalDistance)} />
              <Pressable
                onPress={() => router.push('/comparison')}
                accessibilityRole="button"
                style={({ pressed }) => [styles.compareBtn, pressed && { opacity: 0.65 }]}
              >
                <Text style={styles.compareBtnText}>Compare modes</Text>
                <Feather name="bar-chart-2" size={13} color={colors.primary} />
              </Pressable>
            </View>
          </View>
        )}

        {pairs.map(({ from, to }) => {
          const state = getLegState(from.id, to.id);
          const leg = savedLeg(from.id, to.id, state.mode);
          const isDriving = state.mode === 'driving';
          const steps = state.result?.steps ?? [];

          return (
            <View key={key(from.id, to.id)} style={styles.legCard}>
              {/* From → To header */}
              <View style={styles.legHeader}>
                <View style={styles.endpoint}>
                  <View style={[styles.dot, { backgroundColor: colors.primary }]} />
                  <Text style={styles.endpointName} numberOfLines={1}>{from.name}</Text>
                </View>
                <Feather name="arrow-down" size={14} color={colors.muted} style={{ marginLeft: 10 }} />
                <View style={styles.endpoint}>
                  <View style={[styles.dot, { backgroundColor: colors.secondary }]} />
                  <Text style={styles.endpointName} numberOfLines={1}>{to.name}</Text>
                </View>
              </View>

              {/* Mode selector */}
              <ModeSelector
                value={state.mode}
                onChange={(m) => patch(from.id, to.id, { mode: m, result: null, stepsOpen: false })}
              />

              {isDriving && (
                <View style={styles.drivingWarn}>
                  <Feather name="alert-triangle" size={13} color={colors.drivingWarning} />
                  <Text style={styles.drivingWarnText}>
                    Venue parking closed to spectators during LA28 Games
                  </Text>
                </View>
              )}

              {/* Result row */}
              {leg ? (
                <>
                  <View style={styles.resultRow}>
                    <StatBadge icon="clock" value={formatDuration(leg.duration_s ?? 0)} />
                    <StatBadge icon="map-pin" value={formatDistance(leg.distance_m ?? 0)} />
                    <Pressable
                      onPress={() => fetchDirections(from, to)}
                      disabled={state.loading}
                      hitSlop={8}
                      accessibilityRole="button"
                      accessibilityLabel="Refresh directions"
                      style={({ pressed }) => [styles.refreshBtn, pressed && { opacity: 0.65 }]}
                    >
                      <Feather name="refresh-cw" size={14} color={colors.muted} />
                    </Pressable>
                    <Pressable
                      onPress={() => patch(from.id, to.id, { stepsOpen: !state.stepsOpen })}
                      accessibilityRole="button"
                      style={({ pressed }) => [styles.stepsToggle, pressed && { opacity: 0.65 }]}
                    >
                      <Text style={styles.stepsToggleText}>
                        {state.stepsOpen ? 'Hide steps' : 'Show steps'}
                      </Text>
                      <Feather
                        name={state.stepsOpen ? 'chevron-up' : 'chevron-down'}
                        size={14}
                        color={colors.primary}
                      />
                    </Pressable>
                  </View>
                  <Pressable
                    onPress={() => router.push('/map')}
                    accessibilityRole="button"
                    style={({ pressed }) => [styles.viewMapBtn, pressed && { opacity: 0.8 }]}
                  >
                    <Feather name="map" size={13} color={colors.onPrimary} />
                    <Text style={styles.viewMapBtnText}>View on Map</Text>
                  </Pressable>
                </>
              ) : (
                <Pressable
                  onPress={() => fetchDirections(from, to)}
                  disabled={state.loading}
                  accessibilityRole="button"
                  style={({ pressed }) => [
                    styles.directionsBtn,
                    state.loading && { opacity: 0.5 },
                    pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] },
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
                <Text style={styles.legError} accessibilityRole="alert">{state.error}</Text>
              )}

              {/* Step-by-step directions */}
              {state.stepsOpen && steps.length > 0 && (
                <View style={styles.stepsContainer}>
                  {steps.map((step, i) => (
                    <StepRow key={i} step={step} isLast={i === steps.length - 1} />
                  ))}
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatBadge({ icon, value }: { icon: React.ComponentProps<typeof Feather>['name']; value: string }) {
  return (
    <View style={styles.statBadge}>
      <Feather name={icon} size={13} color={colors.secondary} />
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

function StepRow({ step, isLast }: { step: DirectionStep; isLast: boolean }) {
  const isTransit = step.mode === 'transit';
  const isWalking = step.mode === 'walking';

  const icon: React.ComponentProps<typeof Feather>['name'] = isTransit
    ? (VEHICLE_ICONS[step.transit_vehicle ?? ''] ?? VEHICLE_ICONS.default)
    : isWalking
      ? 'user'
      : 'map-pin';

  const iconColor = isTransit ? colors.secondary : colors.muted;
  const accentColor = step.transit_color ?? colors.secondary;

  return (
    <View style={styles.stepRow}>
      {/* Timeline spine */}
      <View style={styles.stepSpine}>
        <View style={[styles.stepDot, { borderColor: iconColor }]}>
          <Feather name={icon} size={11} color={iconColor} />
        </View>
        {!isLast && <View style={styles.stepLine} />}
      </View>

      <View style={styles.stepContent}>
        {/* Transit: show line name + boarding info */}
        {isTransit && step.transit_line ? (
          <View style={styles.transitStep}>
            <View style={[styles.linePill, { backgroundColor: accentColor }]}>
              <Text style={styles.linePillText}>
                {step.transit_line_short ?? step.transit_line}
              </Text>
            </View>
            <View style={styles.transitBody}>
              <Text style={styles.stepInstruction}>
                {step.transit_line}
                {step.headsign ? ` toward ${step.headsign}` : ''}
              </Text>
              {step.departure_stop && (
                <Text style={styles.stepMeta}>
                  Board at <Text style={styles.stopName}>{step.departure_stop}</Text>
                  {step.arrival_stop ? ` → exit at ` : ''}
                  {step.arrival_stop && (
                    <Text style={styles.stopName}>{step.arrival_stop}</Text>
                  )}
                </Text>
              )}
              {step.num_stops != null && (
                <Text style={styles.stepMeta}>
                  {step.num_stops} {step.num_stops === 1 ? 'stop' : 'stops'}
                  {' · '}
                  {formatDuration(step.duration_s)}
                </Text>
              )}
            </View>
          </View>
        ) : (
          /* Walking / driving step */
          <View style={styles.walkStep}>
            <Text style={styles.stepInstruction}>{step.instruction}</Text>
            {(step.distance_m > 0 || step.duration_s > 0) && (
              <Text style={styles.stepMeta}>
                {step.distance_m > 0 ? formatDistance(step.distance_m) : ''}
                {step.distance_m > 0 && step.duration_s > 0 ? ' · ' : ''}
                {step.duration_s > 0 ? formatDuration(step.duration_s) : ''}
              </Text>
            )}
            {/* Walking sub-steps inside transit legs */}
            {step.sub_steps && step.sub_steps.length > 0 && (
              <View style={styles.subSteps}>
                {step.sub_steps.map((ss, j) => (
                  <Text key={j} style={styles.subStep}>› {ss}</Text>
                ))}
              </View>
            )}
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  scrollContent: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xxl },

  // ── Empty ────────────────────────────────────────────────────────────────
  emptyContainer: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    gap: spacing.md, paddingHorizontal: spacing.xl,
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

  // ── Summary ──────────────────────────────────────────────────────────────
  summaryCard: {
    backgroundColor: colors.surface, borderRadius: radius.md,
    padding: spacing.md, ...shadow.sm,
  },
  summaryLabel: {
    fontFamily: 'Barlow_500Medium', fontSize: 12, color: colors.muted,
    marginBottom: spacing.sm, textTransform: 'uppercase', letterSpacing: 0.5,
  },
  summaryRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  summarySep: { width: 1, height: 16, backgroundColor: colors.border },
  compareBtn: {
    marginLeft: 'auto', flexDirection: 'row', alignItems: 'center',
    gap: 4, paddingVertical: 6, paddingHorizontal: spacing.sm, minHeight: 44,
  },
  compareBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },

  // ── Leg card ─────────────────────────────────────────────────────────────
  legCard: {
    backgroundColor: colors.surface, borderRadius: radius.md,
    padding: spacing.md, gap: spacing.md, ...shadow.sm,
  },
  legHeader: { gap: spacing.xs },
  endpoint: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  dot: { width: 8, height: 8, borderRadius: 4, flexShrink: 0 },
  endpointName: {
    fontFamily: 'Barlow_600SemiBold', fontSize: 14,
    color: colors.foreground, flex: 1,
  },
  drivingWarn: {
    flexDirection: 'row', alignItems: 'flex-start', gap: spacing.xs,
    backgroundColor: '#FEF2F2', borderRadius: radius.sm, padding: spacing.sm,
  },
  drivingWarnText: {
    fontFamily: 'Barlow_400Regular', fontSize: 12,
    color: colors.drivingWarning, flex: 1, lineHeight: 16,
  },

  // ── Result row ───────────────────────────────────────────────────────────
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  statBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: colors.mutedBg, borderRadius: radius.sm,
    paddingHorizontal: spacing.sm, paddingVertical: spacing.xs,
  },
  statValue: { fontFamily: 'BarlowCondensed_600SemiBold', fontSize: 16, color: colors.foreground },
  refreshBtn: {
    padding: spacing.sm, minHeight: 44, minWidth: 44,
    alignItems: 'center', justifyContent: 'center',
  },
  stepsToggle: {
    marginLeft: 'auto', flexDirection: 'row', alignItems: 'center',
    gap: 4, paddingVertical: 6, paddingHorizontal: spacing.sm, minHeight: 44,
  },
  stepsToggleText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
  directionsBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: spacing.sm, backgroundColor: colors.secondary,
    borderRadius: radius.md, paddingVertical: spacing.md, minHeight: 48,
  },
  directionsBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 15, color: colors.onPrimary },
  legError: {
    fontFamily: 'Barlow_400Regular', fontSize: 13,
    color: colors.destructive, textAlign: 'center',
  },
  viewMapBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: spacing.xs, backgroundColor: colors.secondary,
    borderRadius: radius.sm, paddingVertical: 9, paddingHorizontal: spacing.md,
    alignSelf: 'stretch', minHeight: 40,
  },
  viewMapBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.onPrimary },

  // ── Steps ────────────────────────────────────────────────────────────────
  stepsContainer: {
    borderTopWidth: 1, borderTopColor: colors.border,
    paddingTop: spacing.md, gap: 0,
  },
  stepRow: { flexDirection: 'row', gap: spacing.sm, minHeight: 40 },
  stepSpine: { alignItems: 'center', width: 28, paddingTop: 2 },
  stepDot: {
    width: 24, height: 24, borderRadius: 12, borderWidth: 1.5,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.surface, flexShrink: 0,
  },
  stepLine: { flex: 1, width: 1.5, backgroundColor: colors.border, marginTop: 2 },
  stepContent: { flex: 1, paddingBottom: spacing.md },

  // Transit step
  transitStep: { gap: spacing.xs },
  linePill: {
    borderRadius: radius.full, paddingHorizontal: spacing.sm,
    paddingVertical: 3, alignSelf: 'flex-start',
  },
  linePillText: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: '#fff' },
  transitBody: { gap: 2 },
  stepInstruction: {
    fontFamily: 'Barlow_600SemiBold', fontSize: 14,
    color: colors.foreground, lineHeight: 20,
  },
  stopName: { fontFamily: 'Barlow_600SemiBold', color: colors.foreground },
  stepMeta: {
    fontFamily: 'Barlow_400Regular', fontSize: 12,
    color: colors.muted, lineHeight: 16,
  },

  // Walking step
  walkStep: { gap: 2 },
  subSteps: { marginTop: spacing.xs, gap: 2 },
  subStep: {
    fontFamily: 'Barlow_400Regular', fontSize: 12,
    color: colors.muted, lineHeight: 16,
  },
});
