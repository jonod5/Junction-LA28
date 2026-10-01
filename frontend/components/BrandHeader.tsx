// Top bar for the marketing-style screens (welcome, learn-more). The right
// side is left empty on purpose: the global AccountMenu (Survey + Sign in /
// avatar) is docked top-right over every screen and fills that slot.
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import JunctionLogo from '@/components/JunctionLogo';
import { brand, colors, spacing } from '@/constants/theme';

export const CONTENT_MAX_WIDTH = 1120;

interface Props {
  /** Show a back link to the welcome screen instead of the home link. */
  back?: boolean;
}

export function BrandHeader({ back }: Props) {
  const router = useRouter();

  return (
    <View style={styles.bar}>
      <View style={styles.inner}>
        {back ? (
          <Pressable
            onPress={() => (router.canGoBack() ? router.back() : router.replace('/welcome'))}
            accessibilityRole="link"
            style={styles.brand}
          >
            <Feather name="arrow-left" size={20} color={colors.foreground} />
            <Text style={styles.backText}>Back to Junction</Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={() => router.replace('/welcome')}
            accessibilityRole="link"
            accessibilityLabel="Junction home"
            style={styles.brand}
          >
            <JunctionLogo size={32} />
            <Text style={styles.wordmark}>JUNCTION</Text>
            <Text style={styles.tag}>LA28</Text>
          </Pressable>
        )}
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
  backText: { fontFamily: 'Barlow_600SemiBold', fontSize: 16, color: colors.foreground },
});
