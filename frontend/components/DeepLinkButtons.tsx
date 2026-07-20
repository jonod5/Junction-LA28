import { Feather } from '@expo/vector-icons';
import React from 'react';
import { Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/constants/theme';
import type { DeepLink } from '@/lib/deeplinks';

const PROVIDER_ICON: Record<string, React.ComponentProps<typeof Feather>['name']> = {
  uber: 'navigation',
  waymo: 'navigation',
  bird: 'zap',
  spin: 'zap',
  'metro-bike-share': 'navigation',
  'metro-tap': 'credit-card',
};

function open(url: string) {
  // On web, open a new tab so the planner stays put; native hands off to the app.
  if (Platform.OS === 'web') {
    window.open(url, '_blank', 'noopener,noreferrer');
  } else {
    Linking.openURL(url).catch(() => {});
  }
}

interface Props {
  links: DeepLink[];
}

/** Row of "Open in X" hand-off buttons. Renders nothing when there are none. */
export function DeepLinkButtons({ links }: Props) {
  if (links.length === 0) return null;
  return (
    <View style={styles.row}>
      {links.map((link) => (
        <Pressable
          key={link.provider}
          onPress={() => open(link.url)}
          accessibilityRole="link"
          accessibilityLabel={link.label}
          style={({ pressed }) => [styles.btn, pressed && styles.btnPressed]}
        >
          <Feather
            name={PROVIDER_ICON[link.provider] ?? 'external-link'}
            size={13}
            color={colors.primary}
          />
          <Text style={styles.label}>{link.label}</Text>
          <Feather name="external-link" size={11} color={colors.mutedFg} />
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    minHeight: 36,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  btnPressed: { opacity: 0.65 },
  label: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 12,
    color: colors.primary,
  },
});
