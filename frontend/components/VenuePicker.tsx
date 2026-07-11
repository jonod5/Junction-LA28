import { Feather } from '@expo/vector-icons';
import React from 'react';
import {
  FlatList,
  Modal,
  Pressable,
  SafeAreaView,
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
  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
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

        <FlatList
          data={VENUES}
          keyExtractor={(v) => String(v.id)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const disabled = disabledIds.includes(item.id);
            return (
              <Pressable
                onPress={() => !disabled && onSelect(item)}
                accessibilityRole="button"
                accessibilityLabel={`Add ${item.name} to itinerary`}
                accessibilityState={{ disabled }}
                style={({ pressed }) => [
                  styles.card,
                  disabled && styles.cardDisabled,
                  pressed && !disabled && styles.cardPressed,
                ]}
              >
                <View style={styles.cardInner}>
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
                </View>
              </Pressable>
            );
          }}
        />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
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
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadow.sm,
  },
  cardDisabled: {
    opacity: 0.45,
  },
  cardPressed: {
    opacity: 0.75,
    transform: [{ scale: 0.98 }],
  },
  cardInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
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
