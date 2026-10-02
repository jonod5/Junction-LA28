// Top bar for the landing screen. The right
// side is left empty on purpose: the global AccountMenu (Sign in /
// avatar) is docked top-right over every screen and fills that slot.
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import JunctionLogo from '@/components/JunctionLogo';
import { brand, colors, spacing } from '@/constants/theme';

export const CONTENT_MAX_WIDTH = 1120;

export function BrandHeader() {
  const router = useRouter();

  return (
    <View style={styles.bar}>
      <View style={styles.inner}>
        <Pressable
          onPress={() => router.replace('/')}
          accessibilityRole="link"
          accessibilityLabel="Junction home"
          style={styles.brand}
        >
          <JunctionLogo size={32} />
          <Text style={styles.wordmark}>JUNCTION</Text>
          <Text style={styles.tag}>LA28</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  inner: {
    width: '100%',
    maxWidth: CONTENT_MAX_WIDTH,
    alignSelf: 'center',
    minHeight: 64,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  wordmark: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 26,
    letterSpacing: 0.5,
    color: colors.foreground,
  },
  tag: {
    fontFamily: 'Barlow_600SemiBold',
    fontSize: 12,
    color: '#FFFFFF',
    backgroundColor: brand.violet,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    overflow: 'hidden',
  },
});
