import { Feather } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';
import type { CurbDropoff, ParkingOption, TransitAccess, VenueDetail } from '@/lib/api';
import { factRow, type FactRow, parseBusLines, parseLotNames, splitFacts } from '@/lib/venueText';

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

  const moreDetailRows: FactRow[] = venue ? [
    ...splitFacts(venue.congestion_tdm?.general_tdm_notes, 'TDM note'),
    ...splitFacts(venue.congestion_tdm?.arrival_notes, 'Arrival note'),
    ...splitFacts(venue.congestion_tdm?.high_congestion_entry_roads, 'Busy entry roads'),
    ...splitFacts(venue.congestion_tdm?.known_congestion_exit_roads, 'Busy exit roads'),
    ...venue.transit_accesses.flatMap((t) => splitFacts(t.transit_notes)),
  ] : [];

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
        <ScrollView style={styles.scroll} contentContainerStyle={{ gap: spacing.md }} showsVerticalScrollIndicator={false}>
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
            <View style={{ gap: spacing.sm }}>
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

          {/* Remaining detail — progressive disclosure, still a fact list. */}
          {moreDetailRows.length > 0 && (
            <View style={styles.collapseBlock}>
              <Pressable onPress={() => setMoreOpen((v) => !v)} style={styles.collapseHeader} accessibilityRole="button">
                <Feather name={moreOpen ? 'chevron-down' : 'chevron-right'} size={14} color={colors.muted} />
                <Text style={styles.collapseTitle}>More detail</Text>
              </Pressable>
              {moreOpen && (
                <View style={{ gap: 6, paddingLeft: spacing.md, paddingTop: 4 }}>
                  <FactList rows={moreDetailRows} />
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

/** Bold label + terse fragment, one fact per line — the panel-wide row style. */
function FactRowView({ row }: { row: FactRow }) {
  return (
    <Text style={styles.factRowText}>
      <Text style={styles.factLabel}>{row.label}</Text>
      <Text style={styles.factSep}>{'  ·  '}</Text>
      {row.value}
    </Text>
  );
}

function FactList({ rows }: { rows: FactRow[] }) {
  if (rows.length === 0) return null;
  return (
    <View style={styles.factList}>
      {rows.map((row, i) => <FactRowView key={i} row={row} />)}
    </View>
  );
}

function TransitRow({ transit }: { transit: TransitAccess }) {
  // nearest_metro_station often just repeats stop_name for rail entries —
  // only show it when it's actually a different (transfer) station.
  const metroDiffers =
    transit.nearest_metro_station && transit.nearest_metro_station !== transit.stop_name;
  const transferRow = metroDiffers ? factRow('Transfer', transit.nearest_metro_station) : null;
  const busPills = parseBusLines(transit.bus_lines_serving);
  // Not every venue's bus_lines_serving follows the "Line X (to Dest)"
  // pattern the pills need — fall back to a plain fact row so nothing
  // silently disappears.
  const busFallback = busPills.length === 0 ? splitFacts(transit.bus_lines_serving, 'Bus lines') : [];
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
      {transferRow && <FactRowView row={transferRow} />}
      {busPills.length > 0 && (
        <View style={styles.pillRow}>
          {busPills.map((p, i) => (
            <View key={i} style={styles.pill}>
              <Text style={styles.pillText}>{p.code} → {p.detail}</Text>
            </View>
          ))}
        </View>
      )}
      <FactList rows={busFallback} />
    </View>
  );
}

function CurbRow({ curb }: { curb: CurbDropoff }) {
  const rows: FactRow[] = [
    ...splitFacts(curb.rideshare_zone_description, 'Rideshare pickup'),
    ...splitFacts(curb.rideshare_zone_open_window, 'Post-event delay'),
    ...splitFacts(curb.taxi_accessible_zone, 'Accessible zone'),
    ...splitFacts(curb.private_vehicle_dropoff, 'Drop-off'),
  ];
  if (rows.length === 0) return null;
  return (
    <View style={{ gap: spacing.xs }}>
      <Text style={styles.sectionLabel}>DROP-OFF &amp; ACCESSIBILITY</Text>
      <FactList rows={rows} />
    </View>
  );
}

/** Short headline for a multi-lot group: the text before a group label's
 * colon ("Exposition Park: Blue Structure, ...") or a plain lot count. */
function lotGroupLabel(rawLotName: string | null, count: number): string {
  if (rawLotName) {
    const colonIdx = rawLotName.indexOf(':');
    if (colonIdx > -1 && colonIdx < 40) return rawLotName.slice(0, colonIdx).trim();
  }
  return `${count} lots`;
}

function ParkingRow({ parking }: { parking: ParkingOption }) {
  const [lotsOpen, setLotsOpen] = useState(false);
  const hasPrice = parking.price_min != null || parking.price_max != null;
  const priceText = hasPrice
    ? parking.price_min != null && parking.price_max != null
      ? `$${parking.price_min}–$${parking.price_max}`
      : parking.price_min != null
        ? `$${parking.price_min}+`
        : `up to $${parking.price_max}`
    : null;
  const lots = parseLotNames(parking.lot_name);
  const isGroup = lots.length > 1;

  return (
    <View style={styles.parkingBlock}>
      <View style={styles.parkingRow}>
        <Text style={styles.parkingName}>{isGroup ? lotGroupLabel(parking.lot_name, lots.length) : (parking.lot_name ?? 'Lot')}</Text>
        {priceText && <Text style={styles.parkingPrice}>{priceText}</Text>}
      </View>
      {isGroup && (
        <Pressable onPress={() => setLotsOpen((v) => !v)} style={styles.lotsToggle} accessibilityRole="button">
          <Feather name={lotsOpen ? 'chevron-down' : 'chevron-right'} size={12} color={colors.muted} />
          <Text style={styles.lotsToggleText}>{lots.length} lots</Text>
        </Pressable>
      )}
      {isGroup && lotsOpen && (
        <View style={{ paddingLeft: spacing.md, gap: 2 }}>
          {lots.map((lot, i) => <Text key={i} style={styles.lotItem}>{lot}</Text>)}
        </View>
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
  // maxWidth caps a long line name/pill at the panel's width instead of
  // overflowing it — RN's default flexShrink:0 otherwise refuses to shrink
  // and the box just runs past the edge, getting clipped by the panel.
  chip: { maxWidth: '100%', backgroundColor: colors.secondary, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 2 },
  chipText: { fontFamily: 'Barlow_600SemiBold', fontSize: 11, color: colors.onPrimary, flexShrink: 1 },
  transitBlock: { gap: 6, paddingBottom: 2 },
  transitStop: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.foreground },
  transitWalk: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted },
  // Bold-label fact rows — the panel-wide "one fact per line" format.
  factList: { gap: 7 },
  factRowText: { fontFamily: 'Barlow_400Regular', fontSize: 12.5, color: colors.foreground, lineHeight: 18 },
  factLabel: { fontFamily: 'Barlow_700Bold', fontSize: 12.5, color: colors.foreground },
  factSep: { color: colors.muted },
  pillRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 1 },
  pill: { maxWidth: '100%', backgroundColor: colors.mutedBg, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 3 },
  pillText: { fontFamily: 'Barlow_500Medium', fontSize: 11, color: colors.foreground, flexShrink: 1 },
  collapseBlock: { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.xs },
  collapseHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4 },
  collapseTitle: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.muted, flex: 1 },
  parkingBlock: { gap: 4, paddingVertical: 2 },
  parkingRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
  parkingName: { fontFamily: 'Barlow_500Medium', fontSize: 12, color: colors.foreground, flex: 1, lineHeight: 16 },
  parkingPrice: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 14, color: colors.accent },
  lotsToggle: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  lotsToggleText: { fontFamily: 'Barlow_500Medium', fontSize: 11, color: colors.muted },
  lotItem: { fontFamily: 'Barlow_400Regular', fontSize: 11.5, color: colors.muted, lineHeight: 16 },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: colors.eco, borderRadius: radius.md, paddingVertical: spacing.sm, minHeight: 40, marginTop: spacing.xs,
  },
  actionBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 13, color: colors.onPrimary },
});
