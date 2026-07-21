import { Feather } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';
import { ROUTE_MODES } from '@/lib/store';
import type { RouteMode } from '@/lib/api';

const MODE_META: Record<RouteMode, { label: string; icon: React.ComponentProps<typeof Feather>['name'] }> = {
  transit: { label: 'Metro rail & bus', icon: 'navigation' },
  metro_micro: { label: 'Metro Micro', icon: 'grid' },
  bike: { label: 'Bike', icon: 'activity' },
  scooter: { label: 'E-scooter', icon: 'zap' },
  walk: { label: 'Walk', icon: 'user' },
  ridehail: { label: 'Ride-hail', icon: 'truck' },
};

interface Props {
  selected: RouteMode[];
  onChange: (modes: RouteMode[]) => void;
}

/** Checklist of every non-car mode the route engine can rank (FR-U3, FR-R3). */
export function ModePreferencesChecklist({ selected, onChange }: Props) {
  const toggle = (mode: RouteMode) => {
    if (selected.includes(mode)) {
      onChange(selected.filter((m) => m !== mode));
    } else {
      onChange([...selected, mode]);
    }
  };

  return (
    <View style={styles.grid} accessibilityRole="none">
      {ROUTE_MODES.map((mode) => {
        const meta = MODE_META[mode];
        const checked = selected.includes(mode);
        return (
          <Pressable
            key={mode}
            onPress={() => toggle(mode)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked }}
            accessibilityLabel={meta.label}
            style={({ pressed }) => [styles.chip, checked && styles.chipChecked, pressed && styles.chipPressed]}
          >
            <Feather name={meta.icon} size={14} color={checked ? colors.onPrimary : colors.muted} />
            <Text style={[styles.label, checked && styles.labelChecked]}>{meta.label}</Text>
            <Feather
              name={checked ? 'check-circle' : 'circle'}
              size={14}
              color={checked ? colors.onPrimary : colors.border}
            />
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.mutedBg,
    borderWidth: 1.5,
    borderColor: 'transparent',
    minHeight: 40,
  },
  chipChecked: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipPressed: { opacity: 0.8 },
  label: {
    fontFamily: 'Barlow_500Medium',
    fontSize: 13,
    color: colors.muted,
  },
  labelChecked: { color: colors.onPrimary },
});
