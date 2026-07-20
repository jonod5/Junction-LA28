import { Feather } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { DeepLinkButtons } from '@/components/DeepLinkButtons';
import { PolicyBanner } from '@/components/PolicyBanner';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { api, DirectionsResult, type TransitLiveStatus } from '@/lib/api';
import { linksForModes, type Place } from '@/lib/deeplinks';
import { formatDistance, formatDuration } from '@/lib/polyline';
import { useTrip } from '@/lib/store';

const MODES = ['transit', 'walking', 'bicycling', 'driving'] as const;
type Mode = (typeof MODES)[number];

// Which route-engine mode keys each comparison mode maps to for deep links.
const MODE_DEEPLINK_KEYS: Record<Mode, string[]> = {
  transit: ['transit'],
  walking: [],
  bicycling: ['bike', 'scooter'],
  driving: ['ridehail'],
};

const MODE_META: Record<
  Mode,
  {
    icon: React.ComponentProps<typeof Feather>['name'];
    label: string;
    recommended: boolean;
    discouraged: boolean;
    badge?: string;
  }
> = {
  transit: {
    icon: 'navigation',
    label: 'Transit',
    recommended: true,
    discouraged: false,
    badge: 'Recommended',
  },
  walking: { icon: 'user', label: 'Walk', recommended: false, discouraged: false },
  bicycling: { icon: 'activity', label: 'Bike', recommended: false, discouraged: false },
  driving: {
    icon: 'truck',
    label: 'Drive',
    recommended: false,
    discouraged: true,
    badge: 'Discouraged',
  },
};

const GAMES_POLICY =
  'No spectator parking at venues during LA28 Games. Attendees must use transit, sanctioned park-and-ride, or active transport.';

export default function ComparisonScreen() {
  const { trip } = useTrip();
  const params = useLocalSearchParams<{ fromStopId?: string; toStopId?: string }>();

  const stops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);

  // Default to the first pair of stops if no params supplied
  const fromStop = params.fromStopId
    ? stops.find((s) => s.id === Number(params.fromStopId))
    : stops[0];
  const toStop = params.toStopId
    ? stops.find((s) => s.id === Number(params.toStopId))
    : stops[1];

  const [results, setResults] = useState<Partial<Record<Mode, DirectionsResult>>>({});
  const [errors, setErrors] = useState<Partial<Record<Mode, string>>>({});
  const [loadingModes, setLoadingModes] = useState<Set<Mode>>(new Set());
  const [liveStatus, setLiveStatus] = useState<TransitLiveStatus | null>(null);

  // Once transit directions load, ask the backend whether that line is running
  // live right now (Swiftly GTFS-RT). Silent + best-effort — falls back to schedule.
  const transitResult = results.transit;
  useEffect(() => {
    if (!transitResult) { setLiveStatus(null); return; }
    const step = transitResult.steps.find((s) => s.mode === 'transit');
    const line = step?.transit_line_short ?? step?.transit_line;
    if (!line) { setLiveStatus(null); return; }
    let cancelled = false;
    api.getTransitLive(line).then((s) => { if (!cancelled) setLiveStatus(s); }).catch(() => {});
    return () => { cancelled = true; };
  }, [transitResult]);

  useEffect(() => {
    if (!fromStop || !toStop) return;
    const origin = `${fromStop.lat},${fromStop.lng}`;
    const dest = `${toStop.lat},${toStop.lng}`;

    MODES.forEach(async (mode) => {
      setLoadingModes((prev) => new Set([...prev, mode]));
      try {
        const r = await api.getDirections(origin, dest, mode);
        setResults((prev) => ({ ...prev, [mode]: r }));
      } catch (e: unknown) {
        setErrors((prev) => ({
          ...prev,
          [mode]: e instanceof Error ? e.message : 'No route found',
        }));
      } finally {
        setLoadingModes((prev) => {
          const next = new Set(prev);
          next.delete(mode);
          return next;
        });
      }
    });
  }, [fromStop?.id, toStop?.id]);

  if (!fromStop || !toStop) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.center}>
          <Text style={styles.emptyText}>Add at least 2 venues to compare routes.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const originPlace: Place = { lat: fromStop.lat, lng: fromStop.lng, name: fromStop.name };
  const destPlace: Place = { lat: toStop.lat, lng: toStop.lng, name: toStop.name };

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Route header */}
        <View style={styles.routeHeader}>
          <Text style={styles.routeFrom} numberOfLines={1}>
            {fromStop.name}
          </Text>
          <Feather name="arrow-right" size={16} color={colors.muted} />
          <Text style={styles.routeTo} numberOfLines={1}>
            {toStop.name}
          </Text>
        </View>

        {/* LA28 policy banner */}
        <PolicyBanner text={GAMES_POLICY} />

        <Text style={styles.sectionTitle}>Travel Options</Text>

        {/* Mode cards */}
        {MODES.map((mode) => {
          const meta = MODE_META[mode];
          const result = results[mode];
          const error = errors[mode];
          const isLoading = loadingModes.has(mode);

          return (
            <View
              key={mode}
              style={[
                styles.modeCard,
                meta.recommended && styles.modeCardRecommended,
                meta.discouraged && styles.modeCardDiscouraged,
              ]}
            >
              <View style={styles.modeCardHeader}>
                <View
                  style={[
                    styles.modeIcon,
                    meta.recommended && styles.modeIconRecommended,
                    meta.discouraged && styles.modeIconDiscouraged,
                  ]}
                >
                  <Feather
                    name={meta.icon}
                    size={18}
                    color={
                      meta.recommended
                        ? colors.onPrimary
                        : meta.discouraged
                          ? colors.drivingWarning
                          : colors.secondary
                    }
                  />
                </View>
                <Text
                  style={[
                    styles.modeLabel,
                    meta.recommended && styles.modeLabelRecommended,
                    meta.discouraged && styles.modeLabelDiscouraged,
                  ]}
                >
                  {meta.label}
                </Text>
                {meta.badge && (
                  <View
                    style={[
                      styles.badge,
                      meta.recommended ? styles.badgeRecommended : styles.badgeDiscouraged,
                    ]}
                  >
                    <Text
                      style={[
                        styles.badgeText,
                        meta.recommended
                          ? styles.badgeTextRecommended
                          : styles.badgeTextDiscouraged,
                      ]}
                    >
                      {meta.badge}
                    </Text>
                  </View>
                )}
              </View>

              {isLoading && (
                <ActivityIndicator
                  color={meta.recommended ? colors.secondary : colors.muted}
                  size="small"
                  style={styles.loader}
                />
              )}

              {result && !isLoading && (
                <View style={styles.modeResult}>
                  <View style={styles.modeResultItem}>
                    <Feather name="clock" size={14} color={colors.secondary} />
                    <Text style={styles.modeResultValue}>{formatDuration(result.duration_s)}</Text>
                  </View>
                  <View style={styles.modeResultSep} />
                  <View style={styles.modeResultItem}>
                    <Feather name="map-pin" size={14} color={colors.secondary} />
                    <Text style={styles.modeResultValue}>{formatDistance(result.distance_m)}</Text>
                  </View>
                </View>
              )}

              {error && !isLoading && (
                <Text style={styles.modeError}>{error}</Text>
              )}

              {/* Live running status for the transit line (Swiftly GTFS-RT). */}
              {mode === 'transit' && liveStatus?.configured && liveStatus.status !== 'scheduled' && (
                <View style={styles.liveRow}>
                  <View
                    style={[
                      styles.liveDot,
                      { backgroundColor: liveStatus.live ? colors.success : colors.mutedFg },
                    ]}
                  />
                  <Text style={styles.liveText}>
                    {liveStatus.live
                      ? `Live · ${liveStatus.vehicles_running} vehicle${liveStatus.vehicles_running === 1 ? '' : 's'} running now`
                      : 'No live vehicles on this line right now'}
                  </Text>
                </View>
              )}

              {meta.discouraged && (
                <View style={styles.discouragedNote}>
                  <Feather name="alert-triangle" size={13} color={colors.drivingWarning} />
                  <Text style={styles.discouragedNoteText}>
                    Venue parking is closed to spectators during LA28 Games. Driving is not the
                    recommended option.
                  </Text>
                </View>
              )}

              {/* Hand-off links to the relevant apps (no booking here). */}
              <DeepLinkButtons
                links={linksForModes(MODE_DEEPLINK_KEYS[mode], originPlace, destPlace)}
              />
            </View>
          );
        })}

        <View style={styles.footer}>
          <Feather name="info" size={13} color={colors.muted} />
          <Text style={styles.footerText}>
            Times are estimates under normal conditions. Expect higher demand during LA28 Games.
            Always check Metro and event-day shuttle schedules.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  emptyText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 15,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 22,
  },
  scrollContent: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  routeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadow.sm,
  },
  routeFrom: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 14,
    color: colors.foreground,
    flex: 1,
  },
  routeTo: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 14,
    color: colors.foreground,
    flex: 1,
    textAlign: 'right',
  },
  sectionTitle: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 18,
    color: colors.foreground,
    marginBottom: -spacing.xs,
  },
  // ── Mode cards ─────────────────────────────────────────────────────────────
  modeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md,
    ...shadow.sm,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  modeCardRecommended: {
    borderColor: colors.secondary,
    backgroundColor: '#F0FAFE',
  },
  modeCardDiscouraged: {
    borderColor: colors.border,
    opacity: 0.85,
  },
  modeCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  modeIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.mutedBg,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  modeIconRecommended: {
    backgroundColor: colors.secondary,
  },
  modeIconDiscouraged: {
    backgroundColor: '#FEF2F2',
  },
  modeLabel: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 16,
    color: colors.foreground,
    flex: 1,
  },
  modeLabelRecommended: {
    color: colors.secondary,
  },
  modeLabelDiscouraged: {
    color: colors.muted,
  },
  badge: {
    borderRadius: radius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  badgeRecommended: {
    backgroundColor: colors.secondary,
  },
  badgeDiscouraged: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: colors.drivingWarning,
  },
  badgeText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 11,
  },
  badgeTextRecommended: {
    color: colors.onPrimary,
  },
  badgeTextDiscouraged: {
    color: colors.drivingWarning,
  },
  loader: {
    alignSelf: 'flex-start',
  },
  modeResult: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  modeResultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  modeResultValue: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 22,
    color: colors.foreground,
  },
  modeResultSep: {
    width: 1,
    height: 16,
    backgroundColor: colors.border,
  },
  modeError: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
    fontStyle: 'italic',
  },
  liveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  liveText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 12,
    color: colors.foreground,
  },
  discouragedNote: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    backgroundColor: '#FEF2F2',
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  discouragedNoteText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 12,
    color: colors.drivingWarning,
    flex: 1,
    lineHeight: 16,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingTop: spacing.sm,
  },
  footerText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 12,
    color: colors.muted,
    flex: 1,
    lineHeight: 18,
  },
});
