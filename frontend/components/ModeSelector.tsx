import { Feather } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';

export type TravelMode = 'transit' | 'walking' | 'bicycling' | 'driving';

const MODES: { key: TravelMode; icon: React.ComponentProps<typeof Feather>['name']; label: string }[] =
  [
    { key: 'transit', icon: 'navigation', label: 'Transit' },
    { key: 'walking', icon: 'user', label: 'Walk' },
    { key: 'bicycling', icon: 'activity', label: 'Bike' },
    { key: 'driving', icon: 'truck', label: 'Drive' },
  ];

interface Props {
  value: TravelMode;
  onChange: (mode: TravelMode) => void;
}

export function ModeSelector({ value, onChange }: Props) {
  return (
    <View style={styles.row} accessibilityRole="radiogroup" accessibilityLabel="Select travel mode">
      {MODES.map((m) => {
        const active = m.key === value;
        const isDriving = m.key === 'driving';
        return (
          <Pressable
            key={m.key}
            onPress={() => onChange(m.key)}
            style={({ pressed }) => [
              styles.chip,
              active && styles.chipActive,
              isDriving && styles.chipDriving,
              active && isDriving && styles.chipDrivingActive,
              pressed && styles.chipPressed,
            ]}
            accessibilityRole="radio"
            accessibilityState={{ checked: active }}
            accessibilityLabel={`${m.label}${isDriving ? ' — discouraged during LA28 Games' : ''}`}
          >
            <Feather
              name={m.icon}
              size={15}
              color={
                active
                  ? isDriving
                    ? colors.drivingWarning
                    : colors.onPrimary
                  : isDriving
                    ? colors.drivingWarning
                    : colors.muted
              }
            />
            <Text
              style={[
                styles.label,
                active && styles.labelActive,
                isDriving && styles.labelDriving,
              ]}
            >
              {m.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  chip: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.mutedBg,
    borderWidth: 1.5,
    borderColor: 'transparent',
    minHeight: 44,
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipDriving: {
    borderColor: colors.border,
  },
  chipDrivingActive: {
    backgroundColor: '#FEF2F2',
    borderColor: colors.drivingWarning,
  },
  chipPressed: {
    opacity: 0.75,
  },
  label: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 12,
    color: colors.muted,
  },
  labelActive: {
    color: colors.onPrimary,
  },
  labelDriving: {
    color: colors.drivingWarning,
  },
});
