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

import { PolicyBanner } from '@/components/PolicyBanner';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { api, ParkingOption, TransitAccess, VenueDetail } from '@/lib/api';
import { formatDuration } from '@/lib/polyline';

export default function VenueScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [venue, setVenue] = useState<VenueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getVenue(Number(id))
      .then(setVenue)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : 'Could not load venue'),
      )
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !venue) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.center}>
          <Feather name="alert-circle" size={40} color={colors.destructive} />
          <Text style={styles.errorText}>{error ?? 'Venue not found'}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const bestTransit = venue.transit_accesses[0] ?? null;
  const arrivalMin = venue.congestion_tdm?.recommended_arrival_hrs_before_min;
  const arrivalMax = venue.congestion_tdm?.recommended_arrival_hrs_before_max;
  const arrivalNotes = venue.congestion_tdm?.arrival_notes;

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.venueName}>{venue.name}</Text>
          {venue.sport_use && <Text style={styles.sportUse}>{venue.sport_use}</Text>}
          {venue.address && (
            <View style={styles.addressRow}>
              <Feather name="map-pin" size={13} color={colors.muted} />
              <Text style={styles.address}>{venue.address}</Text>
            </View>
          )}
        </View>

        {/* LA28 no-parking policy — prominent, always first */}
        <View style={styles.section}>
          <PolicyBanner text={venue.games_time_parking_policy} />
        </View>

        {/* Games-time access notes */}
        {venue.games_time_access_notes && (
          <View style={styles.section}>
            <SectionHeader icon="compass" title="Games-Time Access" />
            <View style={styles.card}>
              <Text style={styles.bodyText}>{venue.games_time_access_notes}</Text>
            </View>
          </View>
        )}

        {/* Arrival timing */}
        {(arrivalMin != null || arrivalMax != null) && (
          <View style={styles.section}>
            <SectionHeader icon="clock" title="Recommended Arrival" />
            <View style={[styles.card, styles.arrivalCard]}>
              <View style={styles.arrivalBadge}>
                <Feather name="clock" size={16} color={colors.primary} />
                <Text style={styles.arrivalText}>
                  {arrivalMin != null && arrivalMax != null
                    ? `${arrivalMin}–${arrivalMax} hrs before`
                    : arrivalMin != null
                      ? `${arrivalMin}+ hrs before`
                      : `${arrivalMax} hrs before`}
                </Text>
              </View>
              {arrivalNotes && (
                <Text style={[styles.bodyText, styles.arrivalNotes]}>{arrivalNotes}</Text>
              )}
            </View>
          </View>
        )}

        {/* Transit access */}
        {venue.transit_accesses.length > 0 && (
          <View style={styles.section}>
            <SectionHeader icon="navigation" title="Transit Access" />
            {venue.transit_accesses.map((t) => (
              <TransitCard key={t.id} transit={t} />
            ))}
          </View>
        )}

        {/* Parking — normal days only */}
        {venue.parking_options.length > 0 && (
          <View style={styles.section}>
            <SectionHeader icon="truck" title="Parking" />
            <View style={styles.normalDayBanner}>
              <Feather name="info" size={13} color={colors.accent} />
              <Text style={styles.normalDayText}>
                Normal days only — venue parking closed to spectators during LA28 Games
              </Text>
            </View>
            {venue.parking_options.map((p) => (
              <ParkingCard key={p.id} parking={p} />
            ))}
          </View>
        )}

        {/* Congestion notes */}
        {venue.congestion_tdm?.general_tdm_notes && (
          <View style={styles.section}>
            <SectionHeader icon="alert-triangle" title="Congestion & TDM" />
            <View style={styles.card}>
              <Text style={styles.bodyText}>{venue.congestion_tdm.general_tdm_notes}</Text>
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionHeader({
  icon,
  title,
}: {
  icon: React.ComponentProps<typeof Feather>['name'];
  title: string;
}) {
  return (
    <View style={styles.sectionHeader}>
      <Feather name={icon} size={14} color={colors.primary} />
      <Text style={styles.sectionTitle}>{title}</Text>
    </View>
  );
}

function TransitCard({ transit }: { transit: TransitAccess }) {
  return (
    <View style={[styles.card, styles.transitCard]}>
      {transit.line && (
        <View style={styles.transitLine}>
          <View style={styles.lineTag}>
            <Text style={styles.lineTagText}>{transit.line}</Text>
          </View>
          {transit.mode && (
            <Text style={styles.transitMode}>{transit.mode}</Text>
          )}
        </View>
      )}
      {transit.stop_name && (
        <Text style={styles.transitStop}>
          Stop: <Text style={styles.transitStopName}>{transit.stop_name}</Text>
        </Text>
      )}
      {transit.walk_time_min != null && (
        <View style={styles.walkRow}>
          <Feather name="user" size={13} color={colors.muted} />
          <Text style={styles.walkText}>{transit.walk_time_min} min walk to venue</Text>
        </View>
      )}
      {transit.nearest_metro_station && (
        <Text style={styles.metroStation}>
          Nearest Metro: {transit.nearest_metro_station}
        </Text>
      )}
      {transit.bus_lines_serving && (
        <Text style={styles.busLines}>Bus lines: {transit.bus_lines_serving}</Text>
      )}
      {transit.transit_notes && (
        <Text style={styles.transitNotes}>{transit.transit_notes}</Text>
      )}
    </View>
  );
}

function ParkingCard({ parking }: { parking: ParkingOption }) {
  const hasPrice = parking.price_min != null || parking.price_max != null;
  return (
    <View style={[styles.card, styles.parkingCard]}>
      <View style={styles.parkingHeader}>
        {parking.lot_name && (
          <Text style={styles.lotName}>{parking.lot_name}</Text>
        )}
        {hasPrice && (
          <Text style={styles.priceRange}>
            {parking.price_min != null && parking.price_max != null
              ? `$${parking.price_min}–$${parking.price_max}`
              : parking.price_min != null
                ? `$${parking.price_min}+`
                : `up to $${parking.price_max}`}
          </Text>
        )}
      </View>
      {parking.price_notes && (
        <Text style={styles.parkingNotes}>{parking.price_notes}</Text>
      )}
      {parking.pricing_basis && (
        <Text style={styles.parkingBasis}>Source: {parking.pricing_basis}</Text>
      )}
      {parking.notes && (
        <Text style={styles.parkingNotes}>{parking.notes}</Text>
      )}
    </View>
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
    gap: spacing.md,
    padding: spacing.xl,
  },
  errorText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 15,
    color: colors.destructive,
    textAlign: 'center',
  },
  scrollContent: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  // ── Hero ──────────────────────────────────────────────────────────────────
  hero: {
    gap: spacing.xs,
  },
  venueName: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 28,
    color: colors.foreground,
    lineHeight: 32,
  },
  sportUse: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 14,
    color: colors.secondary,
  },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginTop: 2,
  },
  address: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
    flex: 1,
    lineHeight: 18,
  },
  // ── Sections ──────────────────────────────────────────────────────────────
  section: {
    gap: spacing.sm,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  sectionTitle: {
    fontFamily: 'BarlowCondensed_600SemiBold',
    fontSize: 17,
    color: colors.foreground,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadow.sm,
    gap: spacing.xs,
  },
  bodyText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 14,
    color: colors.foreground,
    lineHeight: 20,
  },
  // ── Arrival ───────────────────────────────────────────────────────────────
  arrivalCard: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  arrivalBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  arrivalText: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 20,
    color: colors.foreground,
  },
  arrivalNotes: {
    color: colors.muted,
    marginTop: spacing.xs,
  },
  // ── Transit ───────────────────────────────────────────────────────────────
  transitCard: {
    borderLeftWidth: 3,
    borderLeftColor: colors.secondary,
  },
  transitLine: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  lineTag: {
    backgroundColor: colors.secondary,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  lineTagText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 12,
    color: colors.onPrimary,
  },
  transitMode: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 13,
    color: colors.muted,
    textTransform: 'capitalize',
  },
  transitStop: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 14,
    color: colors.muted,
  },
  transitStopName: {
    fontFamily: 'Barlow_600SemiBold',
    color: colors.foreground,
  },
  walkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  walkText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
  },
  metroStation: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
  },
  busLines: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
  },
  transitNotes: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
    fontStyle: 'italic',
    lineHeight: 18,
  },
  // ── Normal-day parking banner ─────────────────────────────────────────────
  normalDayBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: '#FFFBEB',
    borderWidth: 1,
    borderColor: '#FDE68A',
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  normalDayText: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 12,
    color: '#92400E',
    flex: 1,
    lineHeight: 16,
  },
  // ── Parking card ──────────────────────────────────────────────────────────
  parkingCard: {
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
  },
  parkingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  lotName: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 14,
    color: colors.foreground,
    flex: 1,
  },
  priceRange: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 18,
    color: colors.accent,
  },
  parkingNotes: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 12,
    color: colors.muted,
    lineHeight: 16,
  },
  parkingBasis: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 11,
    color: colors.muted,
    fontStyle: 'italic',
    lineHeight: 15,
  },
});
