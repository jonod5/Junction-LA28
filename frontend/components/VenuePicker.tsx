import { Feather } from '@expo/vector-icons';
import React from 'react';
import {
  Modal,
  Pressable,
  SafeAreaView,
  SectionList,
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

const SECTIONS = [
  { title: 'Airports', data: AIRPORTS as PickerItem[] },
  { title: 'LA28 Venues', data: VENUES as PickerItem[] },
];

export function VenuePicker({ visible, onSelect, onClose, disabledIds = [], disabledNames = [] }: Props) {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
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

        <SectionList
          sections={SECTIONS}
          keyExtractor={(item) => item.kind === 'airport' ? item.code : String(item.id)}
          contentContainerStyle={styles.list}
          renderSectionHeader={({ section }) => (
            <Text style={styles.sectionLabel}>{section.title}</Text>
          )}
          renderItem={({ item }) => {
            const isAirport = item.kind === 'airport';
            const disabled = isAirport
              ? disabledNames.includes(item.name)
              : disabledIds.includes((item as VenueStub).id);

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
                <View style={[
                  styles.iconBadge,
                  { backgroundColor: isAirport ? colors.secondary : colors.primary },
                ]}>
                  <Feather
                    name={isAirport ? 'navigation' : 'map-pin'}
                    size={12}
                    color="#fff"
                  />
                </View>
                <View style={styles.cardText}>
                  {isAirport ? (
                    <View style={styles.nameRow}>
                      <Text style={[styles.itemName, disabled && styles.disabledText]} numberOfLines={1}>
                        {item.name}
                      </Text>
                      <View style={styles.codePill}>
                        <Text style={styles.codeText}>{(item as AirportStub).code}</Text>
                      </View>
                    </View>
                  ) : (
                    <Text style={[styles.itemName, disabled && styles.disabledText]} numberOfLines={1}>
                      {item.name}
                    </Text>
                  )}
                  <Text style={styles.subtitle}>
                    {isAirport
                      ? (item as AirportStub).terminal_info
                      : (item as VenueStub).sport_use}
                  </Text>
                </View>
                {disabled ? (
                  <Text style={styles.addedLabel}>Added</Text>
                ) : (
                  <Feather
                    name="plus-circle"
                    size={20}
                    color={isAirport ? colors.secondary : colors.primary}
                  />
                )}
              </Pressable>
            );
          }}
        />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 22, color: colors.foreground },
  list: { padding: spacing.md, paddingBottom: spacing.xl },
  sectionLabel: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 11,
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
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
  cardPressed: { opacity: 0.75, transform: [{ scale: 0.98 }] },
  iconBadge: {
    width: 28, height: 28, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  cardText: { flex: 1, minWidth: 0 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  itemName: {
    fontFamily: 'Barlow_600SemiBold', fontSize: 15,
    color: colors.foreground, lineHeight: 20, flexShrink: 1,
  },
  codePill: {
    backgroundColor: colors.mutedBg, borderRadius: radius.sm,
    paddingHorizontal: 6, paddingVertical: 1, flexShrink: 0,
  },
  codeText: {
    fontFamily: 'BarlowCondensed_700Bold', fontSize: 11, color: colors.secondary,
  },
  subtitle: {
    fontFamily: 'Barlow_400Regular', fontSize: 13,
    color: colors.muted, marginTop: 2, lineHeight: 18,
  },
  disabledText: { color: colors.muted },
  addedLabel: { fontFamily: 'Barlow_500Medium', fontSize: 12, color: colors.secondary },
});
