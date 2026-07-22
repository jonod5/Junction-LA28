import { Feather } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';
import type { CurbDropoff, ParkingOption, TransitAccess, VenueDetail } from '@/lib/api';

interface Props {
  /** Null while the fetch is still in flight — loading/error states handle it. */
  venue: VenueDetail | null;
  loading: boolean;
  error: string | null;
  /** Live GBFS count near the venue; null while loading/unknown. */
  liveCount: number | null;
  liveLoading: boolean;
  /** Set when the live feed errored — static zones are the fallback. */
  liveError: string | null;
  onClose: () => void;
  /** "Plan route from here" — closes the panel and focuses the itinerary/route panel. */
  onViewRoutes: () => void;
}

/**
 * Compact right-side venue info card, docked over the planner map (FR-I1/I2).
 *
 * Games-first hierarchy: how to get there for the Games, recommended arrival,
 * and live micromobility lead; normal-day parking — the one thing spectators
 * can't use during the car-free Games — is collapsed under an explicit label.
 * All text arrives pre-stripped of provenance asides by the API; this
 * component never renders a source/citation string.
 */
export function VenueDetailPanel({ venue, loading, error, liveCount, liveLoading, liveError, onClose, onViewRoutes }: Props) {
  const [parkingOpen, setParkingOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  const arrivalMin = venue?.congestion_tdm?.recommended_arrival_hrs_before_min;
  const arrivalMax = venue?.congestion_tdm?.recommended_arrival_hrs_before_max;
  const arrivalText =
    arrivalMin != null && arrivalMax != null ? `${arrivalMin}–${arrivalMax} hrs before`
      : arrivalMin != null ? `${arrivalMin}+ hrs before`
      : arrivalMax != null ? `up to ${arrivalMax} hrs before`
      : null;

  const moreDetailParts = venue ? [
    venue.congestion_tdm?.general_tdm_notes,
    venue.congestion_tdm?.arrival_notes,
    ...venue.transit_accesses.map((t) => t.transit_notes).filter(Boolean),
  ].filter((t): t is string => !!t) : [];

  return (
    <div style={PANEL_CSS}>
      <View style={styles.header}>
        <Text style={styles.venueName} numberOfLines={2}>{venue?.name ?? 'Venue'}</Text>
        <Pressable onPress={onClose} hitSlop={10} accessibilityLabel="Close venue details" accessibilityRole="button">
          <Feather name="x" size={20} color={colors.mutedFg} />
        </Pressable>
      </View>
      {venue?.sport_use && <Text style={styles.sportUse}>{venue.sport_use}</Text>}

      {loading || !venue ? (
        <Text style={styles.hint}>Loading venue details…</Text>
      ) : error ? (
        <Text style={styles.errorText}>{error}</Text>
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={{ gap: spacing.sm }} showsVerticalScrollIndicator={false}>
          {/* Live micromobility count — glanceable, top of the card. */}
          <View style={styles.liveRow}>
            <Feather name="zap" size={13} color={liveCount ? colors.success : colors.mutedFg} />
            <Text style={styles.liveText}>
              {liveLoading
                ? 'Checking live scooters/bikes…'
                : liveError
                  ? 'Static zones only — live feed unavailable'
                  : liveCount != null
                    ? `${liveCount} scooter${liveCount === 1 ? '' : 's'}/bike${liveCount === 1 ? '' : 's'} nearby now`
                    : 'No live scooters/bikes nearby right now'}
            </Text>
          </View>

          {/* Hero: how to get there for the Games. */}
          {venue.games_time_access_notes && (
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>HOW TO GET THERE FOR THE GAMES</Text>
              <Text style={styles.heroText}>{venue.games_time_access_notes}</Text>
            </View>
          )}

          {/* Recommended arrival. */}
          {arrivalText && (
            <View style={styles.arrivalRow}>
              <Feather name="clock" size={13} color={colors.primary} />
              <Text style={styles.arrivalText}>Arrive {arrivalText}</Text>
            </View>
          )}

          {/* Transit access — scannable chip rows, not paragraphs. */}
          {venue.transit_accesses.length > 0 && (
            <View style={{ gap: 6 }}>
              <Text style={styles.sectionLabel}>TRANSIT</Text>
              {venue.transit_accesses.map((t) => <TransitRow key={t.id} transit={t} />)}
            </View>
          )}

          {/* Drop-off / rideshare + accessibility — their own short lines. */}
          {venue.curb_dropoffs.map((c) => <CurbRow key={c.id} curb={c} />)}

          {/* Parking — collapsed, explicitly labeled normal-days-only. */}
          {venue.parking_options.length > 0 && (
            <View style={styles.collapseBlock}>
              <Pressable onPress={() => setParkingOpen((v) => !v)} style={styles.collapseHeader} accessibilityRole="button">
                <Feather name={parkingOpen ? 'chevron-down' : 'chevron-right'} size={14} color={colors.muted} />
                <Text style={styles.collapseTitle}>Parking (normal days only — closed to spectators during LA28)</Text>
              </Pressable>
              {parkingOpen && (
                <View style={{ gap: 6, paddingLeft: spacing.md, paddingTop: 4 }}>
                  {venue.parking_options.map((p) => <ParkingRow key={p.id} parking={p} />)}
                </View>
              )}
            </View>
          )}

          {/* Remaining prose — progressive disclosure. */}
          {moreDetailParts.length > 0 && (
            <View style={styles.collapseBlock}>
              <Pressable onPress={() => setMoreOpen((v) => !v)} style={styles.collapseHeader} accessibilityRole="button">
                <Feather name={moreOpen ? 'chevron-down' : 'chevron-right'} size={14} color={colors.muted} />
                <Text style={styles.collapseTitle}>More detail</Text>
              </Pressable>
              {moreOpen && (
                <View style={{ gap: 6, paddingLeft: spacing.md, paddingTop: 4 }}>
                  {moreDetailParts.map((t, i) => <Text key={i} style={styles.proseText}>{t}</Text>)}
                </View>
              )}
            </View>
          )}
        </ScrollView>
      )}

      <Pressable onPress={onViewRoutes} accessibilityRole="button" style={({ pressed }) => [styles.actionBtn, pressed && { opacity: 0.85 }]}>
        <Feather name="navigation" size={14} color={colors.onPrimary} />
        <Text style={styles.actionBtnText}>View route options</Text>
      </Pressable>
    </div>
  );
}

const PANEL_CSS: React.CSSProperties = {
  position: 'absolute', top: 12, right: 12, width: 380,
  maxHeight: 'calc(100% - 24px)', overflowY: 'auto',
  background: 'rgba(255,255,255,0.97)', backdropFilter: 'blur(6px)',
  borderRadius: 14, padding: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.18)', zIndex: 11,
  display: 'flex', flexDirection: 'column', gap: 6,
};

function TransitRow({ transit }: { transit: TransitAccess }) {
  // nearest_metro_station often just repeats stop_name for rail entries —
  // only show it when it's actually a different (transfer) station.
  const metroDiffers =
    transit.nearest_metro_station && transit.nearest_metro_station !== transit.stop_name;
  return (
    <View style={styles.transitBlock}>
      <View style={styles.chipRow}>
        {transit.line && (
          <View style={styles.chip}>
            <Text style={styles.chipText}>{transit.line}</Text>
          </View>
        )}
        {transit.stop_name && <Text style={styles.transitStop}>{transit.stop_name}</Text>}
        {transit.walk_time_min != null && (
          <Text style={styles.transitWalk}>{transit.walk_time_min} min walk</Text>
        )}
      </View>
      {metroDiffers && <Text style={styles.transitSub}>Transfer: {transit.nearest_metro_station}</Text>}
      {transit.bus_lines_serving && <Text style={styles.transitSub}>Bus: {transit.bus_lines_serving}</Text>}
    </View>
  );
}

function CurbRow({ curb }: { curb: CurbDropoff }) {
  const lines: string[] = [];
  if (curb.rideshare_zone_description) {
    lines.push(`Rideshare: ${curb.rideshare_zone_description}${curb.rideshare_zone_open_window ? ` (${curb.rideshare_zone_open_window})` : ''}`);
  }
  if (curb.taxi_accessible_zone) lines.push(`Accessible zone: ${curb.taxi_accessible_zone}`);
  if (curb.private_vehicle_dropoff) lines.push(`Drop-off: ${curb.private_vehicle_dropoff}`);
  if (lines.length === 0) return null;
  return (
    <View style={{ gap: 4 }}>
      <Text style={styles.sectionLabel}>DROP-OFF &amp; ACCESSIBILITY</Text>
      {lines.map((line, i) => (
        <View key={i} style={styles.plainRow}>
          <Feather name="map-pin" size={12} color={colors.muted} style={{ marginTop: 2 }} />
          <Text style={styles.plainRowText}>{line}</Text>
        </View>
      ))}
    </View>
  );
}

function ParkingRow({ parking }: { parking: ParkingOption }) {
  const hasPrice = parking.price_min != null || parking.price_max != null;
  return (
    <View style={styles.parkingRow}>
      <Text style={styles.parkingName}>{parking.lot_name ?? 'Lot'}</Text>
      {hasPrice && (
        <Text style={styles.parkingPrice}>
          {parking.price_min != null && parking.price_max != null
            ? `$${parking.price_min}–$${parking.price_max}`
            : parking.price_min != null ? `$${parking.price_min}+` : `up to $${parking.price_max}`}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
  venueName: { flex: 1, fontFamily: 'BarlowCondensed_700Bold', fontSize: 20, color: colors.foreground, lineHeight: 23 },
  sportUse: { fontFamily: 'Barlow_500Medium', fontSize: 12, color: colors.secondary, marginBottom: 2 },
  hint: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.muted, paddingVertical: spacing.md },
  errorText: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.destructive, paddingVertical: spacing.md },
  scroll: { maxHeight: 420 },
  liveRow: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.mutedBg, borderRadius: radius.sm, padding: spacing.sm },
  liveText: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.foreground, flex: 1 },
  hero: { backgroundColor: '#F0FAFE', borderRadius: radius.sm, padding: spacing.sm, borderLeftWidth: 3, borderLeftColor: colors.secondary, gap: 4 },
  heroLabel: { fontFamily: 'Barlow_700Bold', fontSize: 10, color: colors.secondary, letterSpacing: 0.6 },
  heroText: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.foreground, lineHeight: 18 },
  arrivalRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  arrivalText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.foreground },
  sectionLabel: { fontFamily: 'Barlow_700Bold', fontSize: 10, color: colors.muted, letterSpacing: 0.6 },
  chipRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  chip: { backgroundColor: colors.secondary, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 2 },
  chipText: { fontFamily: 'Barlow_600SemiBold', fontSize: 11, color: colors.onPrimary },
  chipRowText: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, flexShrink: 1 },
  transitBlock: { gap: 3 },
  transitStop: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.foreground },
  transitWalk: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted },
  transitSub: { fontFamily: 'Barlow_400Regular', fontSize: 11.5, color: colors.muted, lineHeight: 16, paddingLeft: 2 },
  plainRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6 },
  plainRowText: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.foreground, flex: 1, lineHeight: 17 },
  collapseBlock: { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.xs },
  collapseHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4 },
  collapseTitle: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.muted, flex: 1 },
  parkingRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
  parkingName: { fontFamily: 'Barlow_500Medium', fontSize: 12, color: colors.foreground, flex: 1, lineHeight: 16 },
  parkingPrice: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 14, color: colors.accent },
  proseText: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, lineHeight: 17 },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.sm, minHeight: 40, marginTop: spacing.xs,
  },
  actionBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 13, color: colors.onPrimary },
});
