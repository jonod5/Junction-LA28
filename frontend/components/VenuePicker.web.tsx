import { Feather } from '@expo/vector-icons';
import React from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';
import { VENUES, VenueStub } from '@/constants/venues';

interface Props {
  visible: boolean;
  onSelect: (venue: VenueStub) => void;
  onClose: () => void;
  disabledIds?: number[];
}

export function VenuePicker({ visible, onSelect, onClose, disabledIds = [] }: Props) {
  if (!visible) return null;

  return (
    // Full-screen overlay rendered as a native View (no Modal) so pointer
    // events work reliably on Expo web.
    <View style={styles.overlay}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close" />

      <View style={styles.sheet}>
        <View style={styles.header}>
          <Text style={styles.title}>Add Venue</Text>
          <Pressable
            onPress={onClose}
            hitSlop={12}
            accessibilityLabel="Close venue picker"
            accessibilityRole="button"
          >
            <Feather name="x" size={24} color={colors.foreground} />
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
          {VENUES.map((item) => {
            const disabled = disabledIds.includes(item.id);
            return (
              <Pressable
                key={item.id}
                onPress={() => {
                  if (!disabled) onSelect(item);
                }}
                accessibilityRole="button"
                accessibilityLabel={`Add ${item.name} to itinerary`}
                accessibilityState={{ disabled }}
                style={({ pressed }) => [
                  styles.card,
                  disabled && styles.cardDisabled,
                  pressed && !disabled && styles.cardPressed,
                ]}
              >
                <View style={styles.dot} />
                <View style={styles.cardText}>
                  <Text style={[styles.venueName, disabled && styles.disabledText]}>
                    {item.name}
                  </Text>
                  <Text style={styles.sportUse}>{item.sport_use}</Text>
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
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 1000,
    justifyContent: 'flex-end',
  },
  backdrop: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  sheet: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    maxHeight: '75%' as any,
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
    gap: spacing.sm,
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
  cardDisabled: {
    opacity: 0.45,
  },
  cardPressed: {
    opacity: 0.75,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.primary,
    flexShrink: 0,
  },
  cardText: {
    flex: 1,
  },
  venueName: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 15,
    color: colors.foreground,
    lineHeight: 20,
  },
  sportUse: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.muted,
    marginTop: 2,
    lineHeight: 18,
  },
  disabledText: {
    color: colors.muted,
  },
  addedLabel: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 12,
    color: colors.secondary,
  },
});
