import { Feather } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text } from 'react-native';

import { gradients, radius, spacing } from '@/constants/theme';

interface Props {
  text: string;
  compact?: boolean;
}

export function PolicyBanner({ text, compact = false }: Props) {
  return (
    <LinearGradient
      colors={gradients.sunset}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 0.3 }}
      style={[styles.banner, compact && styles.compact]}
    >
      <Feather name="alert-circle" size={compact ? 14 : 18} color="#FFFFFF" style={styles.icon} />
      <Text
        style={[styles.text, compact && styles.textCompact]}
        accessibilityRole="text"
        accessibilityLabel={`LA28 policy: ${text}`}
      >
        {text}
      </Text>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  compact: {
    padding: spacing.sm,
    borderRadius: radius.sm,
  },
  icon: {
    marginTop: 1,
    flexShrink: 0,
  },
  text: {
    flex: 1,
    color: '#FFFFFF',
    fontFamily: 'Barlow_400Regular',
    fontSize: 14,
    lineHeight: 20,
  },
  textCompact: {
    fontSize: 12,
    lineHeight: 16,
  },
});
