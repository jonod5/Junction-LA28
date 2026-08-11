import { Feather } from '@expo/vector-icons';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';
import { ROUTE_MODES } from '@/lib/store';
import type { RouteMode } from '@/lib/api';

const MODE_ICON: Record<RouteMode, React.ComponentProps<typeof Feather>['name']> = {
  transit: 'navigation',
  metro_micro: 'grid',
  bike: 'activity',
  scooter: 'zap',
  walk: 'user',
  ridehail: 'truck',
};

interface Props {
  selected: RouteMode[];
  onChange: (modes: RouteMode[]) => void;
}

/** Checklist of every non-car mode the route engine can rank (FR-U3, FR-R3). */
export function ModePreferencesChecklist({ selected, onChange }: Props) {
  const { t } = useTranslation();

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
        const label = t(`modes.${mode}`);
        const checked = selected.includes(mode);
        return (
          <Pressable
            key={mode}
            onPress={() => toggle(mode)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked }}
            accessibilityLabel={label}
            style={({ pressed }) => [styles.chip, checked && styles.chipChecked, pressed && styles.chipPressed]}
          >
            <Feather name={MODE_ICON[mode]} size={14} color={checked ? colors.onPrimary : colors.muted} />
            <Text style={[styles.label, checked && styles.labelChecked]}>{label}</Text>
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
