import { Feather } from '@expo/vector-icons';
import React from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AIRPORTS, AirportStub } from '@/constants/airports';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { VENUES, VenueStub } from '@/constants/venues';

export type PickerItem = VenueStub | AirportStub;

interface Props {
  visible: boolean;
  onSelect: (item: PickerItem) => void;
  onClose: () => void;
  disabledIds?: number[];
  disabledNames?: string[];
}

export function VenuePicker({ visible, onSelect, onClose, disabledIds = [], disabledNames = [] }: Props) {
  if (!visible) return null;

  return (
    <View style={styles.overlay}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close" />

      <View style={styles.sheet}>
        <View style={styles.header}>
          <Text style={styles.title}>Add Stop</Text>
          <Pressable
            onPress={onClose}
            hitSlop={12}
            accessibilityLabel="Close picker"
            accessibilityRole="button"
          >
            <Feather name="x" size={24} color={colors.foreground} />
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
          {/* ── Airports ──────────────────────────────────────────────────── */}
          <Text style={styles.sectionLabel}>Airports</Text>
          {AIRPORTS.map((item) => {
            const disabled = disabledNames.includes(item.name);
            return (
              <Pressable
                key={item.code}
                onPress={() => { if (!disabled) onSelect(item); }}
                accessibilityRole="button"
                accessibilityLabel={`Add ${item.name} to itinerary`}
                accessibilityState={{ disabled }}
                style={({ pressed }) => [
                  styles.card,
                  disabled && styles.cardDisabled,
                  pressed && !disabled && styles.cardPressed,
                ]}
              >
                <View style={[styles.iconBadge, { backgroundColor: colors.secondary }]}>
                  <Feather name="navigation" size={12} color="#fff" />
                </View>
                <View style={styles.cardText}>
                  <View style={styles.nameRow}>
                    <Text style={[styles.itemName, disabled && styles.disabledText]} numberOfLines={1}>
                      {item.name}
                    </Text>
                    <View style={styles.codePill}>
                      <Text style={styles.codeText}>{item.code}</Text>
                    </View>
                  </View>
                  <Text style={styles.subtitle}>{item.terminal_info}</Text>
                </View>
                {disabled ? (
                  <Text style={styles.addedLabel}>Added</Text>
                ) : (
                  <Feather name="plus-circle" size={20} color={colors.secondary} />
                )}
              </Pressable>
            );
          })}

          {/* ── LA28 Venues ───────────────────────────────────────────────── */}
          <Text style={[styles.sectionLabel, { marginTop: spacing.md }]}>LA28 Venues</Text>
          {VENUES.map((item) => {
            const disabled = disabledIds.includes(item.id);
            return (
              <Pressable
                key={item.id}
                onPress={() => { if (!disabled) onSelect(item); }}
                accessibilityRole="button"
                accessibilityLabel={`Add ${item.name} to itinerary`}
                accessibilityState={{ disabled }}
                style={({ pressed }) => [
                  styles.card,
                  disabled && styles.cardDisabled,
                  pressed && !disabled && styles.cardPressed,
                ]}
              >
                <View style={[styles.iconBadge, { backgroundColor: colors.primary }]}>
                  <Feather name="map-pin" size={12} color="#fff" />
                </View>
                <View style={styles.cardText}>
                  <Text style={[styles.itemName, disabled && styles.disabledText]} numberOfLines={1}>
                    {item.name}
                  </Text>
                  <Text style={styles.subtitle}>{item.sport_use}</Text>
                </View>
                {disabled ? (
                  <Text style={styles.addedLabel}>Added</Text>
                ) : (
                  <Feather name="plus-circle" size={20} color={colors.primary} />
                )}
              </Pressable>
            );
          })}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute' as const,
    top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 1000,
    justifyContent: 'flex-end',
  },
  backdrop: {
    position: 'absolute' as const,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  sheet: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    maxHeight: '80%' as any,
    ...shadow.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 22,
    color: colors.foreground,
  },
  list: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  sectionLabel: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 11,
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: spacing.sm,
    marginLeft: 2,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.sm,
  },
  cardDisabled: { opacity: 0.45 },
  cardPressed: { opacity: 0.75 },
  iconBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  cardText: { flex: 1, minWidth: 0 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  itemName: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.foreground,
    lineHeight: 20,
    flexShrink: 1,
  },
  codePill: {
    backgroundColor: colors.mutedBg,
    borderRadius: radius.sm,
    paddingHorizontal: 6,
    paddingVertical: 1,
    flexShrink: 0,
  },
  codeText: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 11,
    color: colors.secondary,
  },
  subtitle: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
    marginTop: 2,
    lineHeight: 18,
  },
  disabledText: { color: colors.muted },
  addedLabel: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 12,
    color: colors.secondary,
  },
});
