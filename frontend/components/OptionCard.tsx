import { Feather } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';

export interface OptionCardMetric {
  icon: React.ComponentProps<typeof Feather>['name'];
  text: string;
}

export type OptionCardVariant = 'default' | 'recommended' | 'discouraged' | 'selected';

interface OptionCardProps {
  icon: React.ComponentProps<typeof Feather>['name'];
  label: string;
  badge?: string;
  variant?: OptionCardVariant;
  /** Flexible icon+value row — travel time, cost, walk time, transfers, etc. */
  metrics?: OptionCardMetric[];
  onPress?: () => void;
  accessibilityLabel?: string;
  /** Anything beyond header/metrics — loading state, error text, a live-status
   * row, a discouraged note, deep-link buttons, a radio indicator. Kept as a
   * slot rather than named props since the two current callers (the mode
   * comparison screen and the SP survey) need different things here. */
  children?: React.ReactNode;
}

const ACCENT_COLOR: Record<OptionCardVariant, string> = {
  default: colors.secondary,
  recommended: colors.secondary,
  discouraged: colors.drivingWarning,
  selected: colors.primary,
};

/**
 * Shared visual shell for "here's one travel option" — used by the mode
 * comparison screen (real routed alternatives) and the SP survey's choice
 * task screen (scenario data, not computed by the route engine). Only the
 * look is shared; each caller supplies its own metrics and extra content.
 */
export function OptionCard({ icon, label, badge, variant = 'default', metrics, onPress, accessibilityLabel, children }: OptionCardProps) {
  const Wrapper = onPress ? Pressable : View;
  const accent = ACCENT_COLOR[variant];

  return (
    <Wrapper
      style={[
        styles.card,
        variant === 'recommended' && styles.cardRecommended,
        variant === 'discouraged' && styles.cardDiscouraged,
        variant === 'selected' && styles.cardSelected,
      ]}
      onPress={onPress}
      accessibilityRole={onPress ? 'radio' : undefined}
      accessibilityState={onPress ? { selected: variant === 'selected' } : undefined}
      accessibilityLabel={accessibilityLabel}
    >
      <View style={styles.header}>
        <View
          style={[
            styles.iconCircle,
            (variant === 'recommended' || variant === 'selected') && { backgroundColor: accent },
            variant === 'discouraged' && styles.iconCircleDiscouraged,
          ]}
        >
          <Feather
            name={icon}
            size={18}
            color={variant === 'recommended' || variant === 'selected' ? colors.onPrimary : accent}
          />
        </View>
        <Text style={[styles.label, (variant === 'recommended' || variant === 'selected') && { color: accent }, variant === 'discouraged' && styles.labelDiscouraged]}>
          {label}
        </Text>
        {badge && (
          <View style={[styles.badge, variant === 'discouraged' ? styles.badgeDiscouraged : { backgroundColor: accent }]}>
            <Text style={[styles.badgeText, variant === 'discouraged' ? styles.badgeTextDiscouraged : styles.badgeTextOnAccent]}>
              {badge}
            </Text>
          </View>
        )}
      </View>

      {metrics && metrics.length > 0 && (
        <View style={styles.metricsRow}>
          {metrics.map((m, i) => (
            <React.Fragment key={i}>
              {i > 0 && <View style={styles.metricsSep} />}
              <View style={styles.metricItem}>
                <Feather name={m.icon} size={14} color={colors.secondary} />
                <Text style={styles.metricValue}>{m.text}</Text>
              </View>
            </React.Fragment>
          ))}
        </View>
      )}

      {children}
    </Wrapper>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md,
    ...shadow.sm,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  cardRecommended: {
    borderColor: colors.secondary,
    backgroundColor: '#F0FAFE',
  },
  cardDiscouraged: {
    borderColor: colors.border,
    opacity: 0.85,
  },
  cardSelected: {
    borderColor: colors.primary,
    backgroundColor: '#EFF6FF',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  iconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.mutedBg,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  iconCircleDiscouraged: {
    backgroundColor: '#FEF2F2',
  },
  label: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 16,
    color: colors.foreground,
    flex: 1,
  },
  labelDiscouraged: {
    color: colors.muted,
  },
  badge: {
    borderRadius: radius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  badgeDiscouraged: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: colors.drivingWarning,
  },
  badgeText: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 11,
  },
  badgeTextOnAccent: {
    color: colors.onPrimary,
  },
  badgeTextDiscouraged: {
    color: colors.drivingWarning,
  },
  metricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  metricItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  metricValue: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 22,
    color: colors.foreground,
  },
  metricsSep: {
    width: 1,
    height: 16,
    backgroundColor: colors.border,
  },
});
