import { Feather } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { DeepLinkButtons } from '@/components/DeepLinkButtons';
import { OptionCard, type OptionCardVariant } from '@/components/OptionCard';
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
    labelKey: string;
    variant: OptionCardVariant;
  }
> = {
  transit: { icon: 'navigation', labelKey: 'comparison.modes.transit', variant: 'recommended' },
  walking: { icon: 'user', labelKey: 'comparison.modes.walk', variant: 'default' },
  bicycling: { icon: 'activity', labelKey: 'comparison.modes.bike', variant: 'default' },
  driving: { icon: 'truck', labelKey: 'comparison.modes.drive', variant: 'discouraged' },
};

export default function ComparisonScreen() {
  const { t, i18n } = useTranslation();
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
        const r = await api.getDirections(origin, dest, mode, i18n.language);
        setResults((prev) => ({ ...prev, [mode]: r }));
      } catch (e: unknown) {
        setErrors((prev) => ({
          ...prev,
          [mode]: e instanceof Error ? e.message : t('comparison.noRouteFound'),
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
          <Text style={styles.emptyText}>{t('comparison.emptyState')}</Text>
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
        <PolicyBanner text={t('common.gamesPolicy')} />

        <Text style={styles.sectionTitle}>{t('comparison.travelOptions')}</Text>

        {/* Mode cards */}
        {MODES.map((mode) => {
          const meta = MODE_META[mode];
          const label = t(meta.labelKey);
          const badge = meta.variant === 'recommended'
            ? t('comparison.badges.recommended')
            : meta.variant === 'discouraged'
              ? t('comparison.badges.discouraged')
              : undefined;
          const result = results[mode];
          const error = errors[mode];
          const isLoading = loadingModes.has(mode);

          return (
            <OptionCard
              key={mode}
              icon={meta.icon}
              label={label}
              badge={badge}
              variant={meta.variant}
              metrics={result && !isLoading ? [
                { icon: 'clock', text: formatDuration(result.duration_s) },
                { icon: 'map-pin', text: formatDistance(result.distance_m) },
              ] : undefined}
            >
              {isLoading && (
                <ActivityIndicator
                  color={meta.variant === 'recommended' ? colors.secondary : colors.muted}
                  size="small"
                  style={styles.loader}
                />
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
                      ? t('comparison.live.running', { count: liveStatus.vehicles_running })
                      : t('comparison.live.none')}
                  </Text>
                </View>
              )}

              {meta.variant === 'discouraged' && (
                <View style={styles.discouragedNote}>
                  <Feather name="alert-triangle" size={13} color={colors.drivingWarning} />
                  <Text style={styles.discouragedNoteText}>
                    {t('comparison.discouragedNote')}
                  </Text>
                </View>
              )}

              {/* Hand-off links to the relevant apps (no booking here). */}
              <DeepLinkButtons
                links={linksForModes(MODE_DEEPLINK_KEYS[mode], originPlace, destPlace)}
              />
            </OptionCard>
          );
        })}

        <View style={styles.footer}>
          <Feather name="info" size={13} color={colors.muted} />
          <Text style={styles.footerText}>{t('comparison.footer')}</Text>
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
  // ── Mode cards — shell styling lives in components/OptionCard.tsx ──────────
  loader: {
    alignSelf: 'flex-start',
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
