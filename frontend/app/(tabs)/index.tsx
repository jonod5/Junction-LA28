import { Feather } from '@expo/vector-icons';
import DraggableFlatList, {
  RenderItemParams,
  ScaleDecorator,
} from 'react-native-draggable-flatlist';
import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { PickerItem, VenuePicker } from '@/components/VenuePicker';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { Stop } from '@/lib/api';
import { useTrip } from '@/lib/store';

// Olympic ring colors (L→R: blue, yellow, black, green, red)
const RING_COLORS = ['#0085C7', '#F4C300', '#1A1A1A', '#009F3D', '#DF0024'];

export default function BuilderScreen() {
  const { trip, loading, error, clearError, createTrip, addStop, removeStop, reorderStops } =
    useTrip();
  const router = useRouter();

  const [tripName, setTripName] = useState('My LA28 Trip');
  const [creating, setCreating] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  // Floating icon animation for empty state
  const floatAnim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim, {
          toValue: -10,
          duration: 1800,
          useNativeDriver: true,
          easing: Easing.inOut(Easing.sin),
        }),
        Animated.timing(floatAnim, {
          toValue: 0,
          duration: 1800,
          useNativeDriver: true,
          easing: Easing.inOut(Easing.sin),
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [floatAnim]);

  const addedVenueIds = trip?.stops
    .map((s) => s.venue_id)
    .filter((id): id is number => id !== null) ?? [];
  const addedNames = trip?.stops.map((s) => s.name) ?? [];

  const handleCreateTrip = async () => {
    setCreating(true);
    const name = tripName.trim() || 'My LA28 Trip';
    await createTrip(name);
    setCreating(false);
  };

  const handleSelectStop = useCallback(
    async (item: PickerItem) => {
      setPickerOpen(false);
      const venueId = item.kind === 'venue' ? item.id : null;
      await addStop(venueId, item.name, item.lat, item.lng);
    },
    [addStop],
  );

  const handleRemove = (stop: Stop) => {
    Alert.alert('Remove Stop', `Remove ${stop.name} from your itinerary?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => removeStop(stop.id),
      },
    ]);
  };

  const handleDragEnd = useCallback(
    ({ data }: { data: Stop[] }) => {
      const order = data.map((s, i) => ({ stop_id: s.id, order_index: i }));
      reorderStops(order);
    },
    [reorderStops],
  );

  const renderStop = useCallback(
    ({ item, drag, isActive }: RenderItemParams<Stop>) => (
      <ScaleDecorator>
        <Pressable
          onLongPress={drag}
          delayLongPress={150}
          accessibilityLabel={`${item.name}, long press to reorder`}
          style={[styles.stopCard, isActive && styles.stopCardDragging]}
        >
          <Feather name="menu" size={16} color={colors.mutedFg} style={styles.dragHandle} />
          <View style={styles.stopBadge}>
            <Text style={styles.stopBadgeText}>
              {(trip?.stops.findIndex((s) => s.id === item.id) ?? 0) + 1}
            </Text>
          </View>
          <View style={styles.stopInfo}>
            <Text style={styles.stopName} numberOfLines={1}>
              {item.name}
            </Text>
          </View>
          <Pressable
            onPress={() => handleRemove(item)}
            hitSlop={12}
            accessibilityLabel={`Remove ${item.name}`}
            accessibilityRole="button"
          >
            <Feather name="x-circle" size={20} color={colors.mutedFg} />
          </Pressable>
        </Pressable>
      </ScaleDecorator>
    ),
    [trip, handleRemove],
  );

  // ── No trip yet — creation form ────────────────────────────────────────────
  if (!trip) {
    // Web gradient style applied inline to bypass StyleSheet type constraints
    const webGradient = Platform.OS === 'web'
      ? ({ background: 'linear-gradient(135deg, #0F3BBE 0%, #2563EB 100%)' } as any)
      : {};

    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.emptyContainer}>

          {/* Olympic rings */}
          <View style={styles.olympicRings}>
            {RING_COLORS.map((c, i) => (
              <View
                key={i}
                style={[styles.ring, { borderColor: c }, i > 0 && styles.ringOverlap]}
              />
            ))}
          </View>

          {/* Floating torch icon */}
          <Animated.View style={[styles.emptyIconWrap, { transform: [{ translateY: floatAnim }] }]}>
            <View style={styles.emptyIconBg}>
              <Feather name="map-pin" size={36} color="#FFFFFF" />
            </View>
          </Animated.View>

          <Text style={styles.emptyTitle}>PLAN YOUR{'\n'}OLYMPIC JOURNEY</Text>
          <Text style={styles.emptySubtitle}>
            Build a custom itinerary across LA28 venues — add stops, get transit routes, and
            navigate LA like a pro.
          </Text>

          <View style={styles.createForm}>
            <Text style={styles.inputLabel}>Trip name</Text>
            <TextInput
              style={styles.input}
              value={tripName}
              onChangeText={setTripName}
              placeholder="My LA28 Trip"
              placeholderTextColor={colors.mutedFg}
              returnKeyType="done"
              accessibilityLabel="Trip name"
            />
            <Pressable
              onPress={handleCreateTrip}
              disabled={creating || loading}
              accessibilityRole="button"
              accessibilityLabel="Create trip"
              style={({ pressed }) => [
                styles.primaryBtn,
                webGradient,
                (creating || loading) && styles.primaryBtnDisabled,
                pressed && styles.primaryBtnPressed,
              ]}
            >
              {creating || loading ? (
                <ActivityIndicator color={colors.onPrimary} size="small" />
              ) : (
                <>
                  <Feather name="plus" size={18} color={colors.onPrimary} />
                  <Text style={styles.primaryBtnText}>Create Trip</Text>
                </>
              )}
            </Pressable>
            {error && (
              <Text style={styles.errorText} accessibilityRole="alert">
                {error}
              </Text>
            )}
          </View>
        </View>
      </SafeAreaView>
    );
  }

  const stops = [...(trip.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
  const webGradient = Platform.OS === 'web'
    ? ({ background: 'linear-gradient(135deg, #0F3BBE 0%, #2563EB 100%)' } as any)
    : {};

  return (
    <SafeAreaView style={styles.screen}>
      {/* Trip name bar */}
      <View style={styles.tripBar}>
        <View style={styles.tripBarLeft}>
          <View style={styles.tripBarAccent} />
          <Text style={styles.tripName} numberOfLines={1}>
            {trip.name}
          </Text>
        </View>
        <View style={styles.stopCountBadge}>
          <Text style={styles.stopCountText}>
            {stops.length} {stops.length === 1 ? 'stop' : 'stops'}
          </Text>
        </View>
      </View>

      {error && (
        <Pressable onPress={clearError} style={styles.errorBanner}>
          <Feather name="alert-circle" size={14} color={colors.destructive} />
          <Text style={styles.errorBannerText}>{error}</Text>
        </Pressable>
      )}

      {/* Stop list */}
      {stops.length === 0 ? (
        <View style={styles.listEmpty}>
          <Feather name="plus-circle" size={40} color={colors.border} />
          <Text style={styles.listEmptyText}>No stops yet</Text>
          <Text style={styles.listEmptyHint}>Tap "Add Stop" to build your itinerary</Text>
        </View>
      ) : (
        <DraggableFlatList
          data={stops}
          onDragEnd={handleDragEnd}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderStop}
          contentContainerStyle={styles.listContent}
        />
      )}

      {/* Footer actions */}
      <View style={styles.footer}>
        {loading && <ActivityIndicator color={colors.primary} style={styles.footerLoader} />}
        <Pressable
          onPress={() => setPickerOpen(true)}
          disabled={stops.length >= 10}
          accessibilityRole="button"
          accessibilityLabel="Add stop to itinerary"
          style={({ pressed }) => [
            styles.addBtn,
            webGradient,
            stops.length >= 10 && styles.addBtnDisabled,
            pressed && styles.addBtnPressed,
          ]}
        >
          <Feather name="plus" size={18} color={colors.onPrimary} />
          <Text style={styles.addBtnText}>Add Stop</Text>
        </Pressable>

        {stops.length >= 2 && (
          <Pressable
            onPress={() => router.push('/routes')}
            accessibilityRole="button"
            accessibilityLabel="View routes between venues"
            style={({ pressed }) => [styles.routesBtn, pressed && styles.routesBtnPressed]}
          >
            <Text style={styles.routesBtnText}>View Routes</Text>
            <Feather name="arrow-right" size={16} color={colors.gold} />
          </Pressable>
        )}
      </View>

      <VenuePicker
        visible={pickerOpen}
        onSelect={handleSelectStop}
        onClose={() => setPickerOpen(false)}
        disabledIds={addedVenueIds}
        disabledNames={addedNames}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },

  // ── Empty / Create ────────────────────────────────────────────────────────
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
  },
  olympicRings: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  ring: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 3,
  },
  ringOverlap: {
    marginLeft: -10,
  },
  emptyIconWrap: {
    marginBottom: spacing.lg,
  },
  emptyIconBg: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadow.md,
  },
  emptyTitle: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 36,
    color: colors.foreground,
    textAlign: 'center',
    letterSpacing: 2,
    lineHeight: 40,
    marginBottom: spacing.sm,
  },
  emptySubtitle: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 15,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.xl,
  },
  createForm: {
    width: '100%',
    gap: spacing.sm,
  },
  inputLabel: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 12,
    color: colors.muted,
    marginBottom: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontFamily: 'Barlow_400Regular',
    fontSize: 16,
    color: colors.foreground,
    minHeight: 48,
  },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    minHeight: 52,
    marginTop: spacing.xs,
  },
  primaryBtnDisabled: {
    opacity: 0.5,
  },
  primaryBtnPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.97 }],
  },
  primaryBtnText: {
    fontFamily: 'Barlow_700Bold',
    fontSize: 16,
    color: colors.onPrimary,
    letterSpacing: 0.5,
  },
  errorText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.destructive,
    textAlign: 'center',
    marginTop: spacing.xs,
  },

  // ── Trip view ─────────────────────────────────────────────────────────────
  tripBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  tripBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
  },
  tripBarAccent: {
    width: 3,
    height: 22,
    borderRadius: 2,
    backgroundColor: colors.primary,
    flexShrink: 0,
  },
  tripName: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 20,
    color: colors.foreground,
    letterSpacing: 1,
    flex: 1,
  },
  stopCountBadge: {
    backgroundColor: colors.mutedBg,
    borderRadius: radius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  stopCountText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 12,
    color: colors.primary,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: '#FEF2F2',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    borderRadius: radius.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.destructive,
  },
  errorBannerText: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.destructive,
    flex: 1,
  },
  listContent: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xxl,
  },
  listEmpty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  listEmptyText: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 20,
    color: colors.mutedFg,
    letterSpacing: 1,
  },
  listEmptyHint: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 14,
    color: colors.mutedFg,
  },

  // ── Stop card ─────────────────────────────────────────────────────────────
  stopCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md,
    ...shadow.sm,
    marginBottom: spacing.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  stopCardDragging: {
    ...shadow.md,
    transform: [{ scale: 1.03 }],
    borderLeftColor: colors.gold,
  },
  dragHandle: {
    flexShrink: 0,
  },
  stopBadge: {
    width: 32,
    height: 32,
    borderRadius: radius.full,
    backgroundColor: colors.gold,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  stopBadgeText: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 15,
    color: '#1A0A00',
  },
  stopInfo: {
    flex: 1,
  },
  stopName: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.foreground,
  },

  // ── Footer ────────────────────────────────────────────────────────────────
  footer: {
    padding: spacing.md,
    paddingBottom: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    gap: spacing.sm,
  },
  footerLoader: {
    alignSelf: 'center',
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    minHeight: 52,
  },
  addBtnDisabled: {
    opacity: 0.4,
  },
  addBtnPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.97 }],
  },
  addBtnText: {
    fontFamily: 'Barlow_700Bold',
    fontSize: 16,
    color: colors.onPrimary,
    letterSpacing: 0.5,
  },
  routesBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    minHeight: 44,
    borderWidth: 1.5,
    borderColor: colors.gold,
    borderRadius: radius.md,
  },
  routesBtnPressed: {
    opacity: 0.65,
  },
  routesBtnText: {
    fontFamily: 'Barlow_700Bold',
    fontSize: 15,
    color: colors.gold,
    letterSpacing: 0.5,
  },
});
