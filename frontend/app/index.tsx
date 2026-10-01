// Landing screen (the app's entry route): what Junction is, plus entry
// points to the planner, the SP survey, sign-in and the learn-more page.
import { Feather } from '@expo/vector-icons';
import { useRouter, type Href } from 'expo-router';
import React from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { BrandHeader, CONTENT_MAX_WIDTH } from '@/components/BrandHeader';
import { brand, colors, radius, spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

const SCREENSHOT = require('@/assets/images/landing/app-screenshot.png');
const HUMAN_LAB = require('@/assets/images/landing/human-lab.png');

type ActionCard = {
  /** A route to open, or 'sign-in' to start Google sign-in in place. */
  target: Href | 'sign-in';
  icon: React.ComponentProps<typeof Feather>['name'];
  title: string;
  body: string;
  cta: string;
  variant: 'primary' | 'secondary' | 'plain' | 'outline';
};

const MAP: ActionCard = {
  target: '/home',
  icon: 'map',
  title: 'Open the map',
  body: 'Compare routes to any venue.',
  cta: 'Start planning →',
  variant: 'primary',
};

const SURVEY: ActionCard = {
  target: '/survey',
  icon: 'clipboard',
  title: 'Take the survey',
  body: 'Help UCLA research Games travel.',
  cta: 'Begin survey →',
  variant: 'secondary',
};

const SIGN_IN: ActionCard = {
  target: 'sign-in',
  icon: 'log-in',
  title: 'Sign in',
  body: 'Save and revisit your trips.',
  cta: 'Continue with Google →',
  variant: 'plain',
};

// Signed-in users get a shortcut to their trips in the same slot.
const MY_TRIPS: ActionCard = {
  target: '/itineraries',
  icon: 'bookmark',
  title: 'My trips',
  body: 'Your saved itineraries.',
  cta: 'View trips →',
  variant: 'plain',
};

const LEARN_MORE: ActionCard = {
  target: '/learn-more',
  icon: 'info',
  title: 'How it works',
  body: 'Features, modes and apps to get.',
  cta: 'Learn more →',
  variant: 'outline',
};

export default function LandingScreen() {
  const router = useRouter();
  const { user, isConfigured, signInWithGoogle } = useAuth();
  // Hide the account slot entirely when no Supabase project is configured.
  const accountCard = !isConfigured ? null : user ? MY_TRIPS : SIGN_IN;
  const actions = [MAP, SURVEY, accountCard, LEARN_MORE].filter((a): a is ActionCard => a !== null);
  const { width } = useWindowDimensions();
  const wide = width >= 860;

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.pageContent}>
      <BrandHeader />

      <View style={[styles.container, styles.hero, wide && styles.heroWide]}>
        <View style={[styles.heroCopy, wide && styles.half]}>
          <Text style={[styles.h1, { fontSize: wide ? 76 : 48, lineHeight: wide ? 72 : 46 }]}>
            EVERY VENUE.{'\n'}
            <Text style={{ color: colors.primary }}>NO CAR NEEDED.</Text>
          </Text>
          <Text style={styles.lede}>
            Plan transit, bike, scooter and ride-hail trips to every LA28 venue.
          </Text>
        </View>

        <View style={[styles.phoneWrap, wide && styles.half]}>
          <View style={styles.phone}>
            <Image
              source={SCREENSHOT}
              style={styles.screenshot}
              resizeMode="cover"
              accessibilityLabel="Junction on a phone: a route from LAX to SoFi Stadium drawn on the map, with ranked options below and Metro Micro marked best"
            />
          </View>
        </View>
      </View>

      <View style={[styles.container, styles.actions]}>
        {actions.map((a) => {
          const v = variantStyles[a.variant];
          return (
            <Pressable
              key={a.title}
              onPress={() => (a.target === 'sign-in' ? signInWithGoogle() : router.push(a.target))}
              accessibilityRole="link"
              style={({ pressed }) => [styles.card, v.card, pressed && styles.cardPressed]}
            >
              <Feather name={a.icon} size={32} color={v.iconColor} />
              <Text style={[styles.cardTitle, { color: v.titleColor }]}>{a.title}</Text>
              <Text style={[styles.cardBody, { color: v.bodyColor }]}>{a.body}</Text>
              <Text style={[styles.cardCta, { color: v.ctaColor }]}>{a.cta}</Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.footer}>
        <View style={[styles.container, styles.footerInner]}>
          <Image
            source={HUMAN_LAB}
            style={styles.labLogo}
            resizeMode="contain"
            accessibilityLabel="HUMAN Lab: Human Understanding in Mobility and Automation in Networks"
          />
          <Text style={styles.footerText}>English · Español · Français · 中文</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const variantStyles = {
  primary: {
    card: { backgroundColor: colors.primary },
    iconColor: '#FFFFFF',
    titleColor: '#FFFFFF',
    bodyColor: colors.mutedBg,
    ctaColor: '#FFFFFF',
  },
  secondary: {
    card: { backgroundColor: '#7E22CE' },
    iconColor: '#FFFFFF',
    titleColor: '#FFFFFF',
    bodyColor: '#F3E8FF',
    ctaColor: '#FFFFFF',
  },
  plain: {
    card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
    iconColor: colors.primary,
    titleColor: colors.foreground,
    bodyColor: colors.muted,
    ctaColor: colors.primary,
  },
  outline: {
    card: { backgroundColor: colors.surface, borderWidth: 2, borderColor: brand.gold },
    iconColor: '#B45309',
    titleColor: colors.foreground,
    bodyColor: colors.muted,
    ctaColor: '#B45309',
  },
} as const;

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background },
  pageContent: { flexGrow: 1 },
  container: {
    width: '100%',
    maxWidth: CONTENT_MAX_WIDTH,
    alignSelf: 'center',
    paddingHorizontal: spacing.md,
  },
  half: { flex: 1 },

  hero: { paddingTop: 48, paddingBottom: 32, gap: 40 },
  heroWide: { flexDirection: 'row', alignItems: 'center' },
  heroCopy: { gap: 20 },
  h1: { fontFamily: 'BarlowCondensed_700Bold', color: colors.foreground },
  lede: { fontFamily: 'Barlow_400Regular', fontSize: 19, lineHeight: 28, color: colors.muted, maxWidth: 520 },

  phoneWrap: { alignItems: 'center' },
  phone: {
    padding: 10,
    borderRadius: 40,
    backgroundColor: colors.foreground,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.25,
    shadowRadius: 48,
    elevation: 8,
  },
  // Explicit size: react-native-web ignores aspectRatio on <Image>.
  screenshot: { width: 300, height: 300 * (1688 / 1000), borderRadius: 30 },

  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: 64,
  },
  card: {
    flexGrow: 1,
    flexBasis: 240,
    minHeight: 200,
    padding: spacing.lg,
    borderRadius: radius.lg,
    gap: 14,
  },
  cardPressed: { opacity: 0.85 },
  cardTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 30, textTransform: 'uppercase' },
  cardBody: { fontFamily: 'Barlow_400Regular', fontSize: 16, lineHeight: 23, flexGrow: 1 },
  cardCta: { fontFamily: 'Barlow_600SemiBold', fontSize: 15 },

  footer: {
    marginTop: 'auto',
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  footerInner: {
    paddingVertical: 20,
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  labLogo: { height: 64, width: 64 * (800 / 313) },
  footerText: { fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.muted },
});
