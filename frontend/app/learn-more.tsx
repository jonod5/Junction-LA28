// Learn-more screen: features, transport modes, and the companion apps
// Junction hands off to. Static content, English-only for now.
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useRef } from 'react';
import {
  Image,
  type ImageSourcePropType,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { BrandHeader, CONTENT_MAX_WIDTH } from '@/components/BrandHeader';
import { brand, colors, radius, spacing } from '@/constants/theme';

const FEATURES: { icon: React.ComponentProps<typeof Feather>['name']; title: string; body: string }[] = [
  { icon: 'list', title: 'Ranked route options', body: 'Every option is scored on travel time, cost and transfers, weighted by the modes you prefer.' },
  { icon: 'activity', title: 'Live data', body: 'Real-time Metro vehicle positions and live bike and scooter availability near you.' },
  { icon: 'map-pin', title: 'Venue guides', body: 'Drop-off zones, nearest stations and crowding notes for each venue, verified by hand.' },
  { icon: 'external-link', title: 'One-tap hand-off', body: "Opens Uber, Waymo, Bird or Metro when you're ready to ride." },
  { icon: 'bookmark', title: 'Saved itineraries', body: 'Sign in with Google to save, tag and pin trips, sorted into upcoming and past.' },
  { icon: 'globe', title: 'Four languages', body: 'English, Spanish, French and Simplified Chinese, including step-by-step directions.' },
];

const TINT = {
  violet: { bg: '#F3E8FF', fg: '#7E22CE' },
  blue: { bg: colors.mutedBg, fg: colors.primary },
  green: { bg: '#DDF3E6', fg: '#1F6F43' },
  amber: { bg: '#FEF3C7', fg: '#92400E' },
} as const;

const MODES: {
  icon: React.ComponentProps<typeof MaterialCommunityIcons>['name'];
  tint: keyof typeof TINT;
  title: string;
  body: string;
  app: string;
}[] = [
  { icon: 'train', tint: 'violet', title: 'Metro Rail & Bus', body: 'The backbone of most trips. Frequent service to venue areas on Games days.', app: 'Pay with: TAP card or TAP app' },
  { icon: 'walk', tint: 'blue', title: 'Walking', body: 'First and last stretch to the gate, with step-by-step directions.', app: 'No app needed' },
  { icon: 'bicycle', tint: 'green', title: 'Metro Bike Share', body: 'Dock-based bikes for short hops to and from stations. Live dock availability shown.', app: 'Unlock with: Metro Bike app' },
  { icon: 'scooter', tint: 'green', title: 'Bird scooters', body: 'Dockless e-scooters to cut walking time between destinations.', app: 'Unlock with: Bird app' },
  { icon: 'van-passenger', tint: 'violet', title: 'Metro Micro', body: 'On-demand shared vans. Only offered when your trip starts inside a service zone.', app: 'Book with: Metro Micro app' },
  { icon: 'car', tint: 'amber', title: 'Ride-hail', body: 'Door to a designated drop-off zone — not the venue gate. Junction routes you to the right zone.', app: 'Book with: Uber or Waymo' },
  { icon: 'parking', tint: 'blue', title: 'Park & ride', body: 'Drive to an outlying Metro lot, then ride transit the rest of the way in.', app: 'Pay with: TAP card or TAP app' },
];

type AppEntry = { name: string; body: string; logo: ImageSourcePropType; crop?: boolean };

const APP_GROUPS: { title: string; color: string; apps: AppEntry[] }[] = [
  {
    title: 'Ride-hail',
    color: '#92400E',
    apps: [
      // The Uber asset ships with wide white padding; crop it to the mark.
      { name: 'Uber', body: "Rides to the venue's designated drop-off zone.", logo: require('@/assets/images/landing/uber.png'), crop: true },
      { name: 'Waymo', body: 'Driverless rides where Waymo operates.', logo: require('@/assets/images/landing/waymo.png') },
    ],
  },
  {
    title: 'Bikes & scooters',
    color: '#1F6F43',
    apps: [
      { name: 'Bird', body: 'Junction shows nearby scooters and opens Bird to unlock one.', logo: require('@/assets/images/landing/bird.png') },
      { name: 'Metro Bike Share', body: 'Junction points you to a dock with bikes available; unlock in the Metro Bike app.', logo: require('@/assets/images/landing/metro-bike.png') },
    ],
  },
  {
    title: 'Transit',
    color: '#7E22CE',
    apps: [
      { name: 'LA Metro / TAP', body: 'Load fare onto a TAP card or the TAP app to ride Metro Rail, bus and park & ride.', logo: require('@/assets/images/landing/la-metro.png') },
      { name: 'Metro Micro', body: 'Book an on-demand van when Junction finds you inside a Metro Micro zone.', logo: require('@/assets/images/landing/metro-micro.png') },
    ],
  },
];

type SectionKey = 'features' | 'modes' | 'apps';

export default function LearnMoreScreen() {
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const offsets = useRef<Record<SectionKey, number>>({ features: 0, modes: 0, apps: 0 });

  const jumpTo = (key: SectionKey) =>
    scrollRef.current?.scrollTo({ y: Math.max(offsets.current[key] - spacing.md, 0), animated: true });
  const track = (key: SectionKey) => (e: { nativeEvent: { layout: { y: number } } }) => {
    offsets.current[key] = e.nativeEvent.layout.y;
  };

  return (
    <ScrollView ref={scrollRef} style={styles.page} contentContainerStyle={styles.pageContent}>
      <BrandHeader back />

      <View style={styles.container}>
        <View style={styles.chips}>
          {([
            ['features', 'Features'],
            ['modes', 'Transport modes'],
            ['apps', 'Apps to download'],
          ] as [SectionKey, string][]).map(([key, label]) => (
            <Pressable key={key} onPress={() => jumpTo(key)} accessibilityRole="link" style={styles.chip}>
              <Text style={styles.chipText}>{label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.intro}>
          <Text style={styles.eyebrow}>HOW IT WORKS</Text>
          <Text style={styles.h1}>PLAN HERE.{'\n'}RIDE ANYWHERE.</Text>
          <Text style={styles.lede}>
            No spectator parking at LA28 venues. Junction finds your best car-free route, then opens the app to pay or book.
          </Text>
        </View>

        <View style={styles.section} onLayout={track('features')}>
          <Text style={styles.h2}>FEATURES</Text>
          <View style={styles.grid}>
            {FEATURES.map((f) => (
              <View key={f.title} style={[styles.card, styles.featureCard]}>
                <Feather name={f.icon} size={28} color={colors.primary} />
                <Text style={styles.h3}>{f.title}</Text>
                <Text style={styles.body}>{f.body}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.section} onLayout={track('modes')}>
          <Text style={styles.h2}>TRANSPORT MODES</Text>
          <Text style={styles.sectionLede}>
            Junction mixes these within one trip — for example, a scooter to the station, Metro across town, then a short walk.
          </Text>
          <View style={styles.grid}>
            {MODES.map((m) => (
              <View key={m.title} style={[styles.card, styles.modeCard]}>
                <View style={[styles.modeIcon, { backgroundColor: TINT[m.tint].bg }]}>
                  <MaterialCommunityIcons name={m.icon} size={26} color={TINT[m.tint].fg} />
                </View>
                <View style={styles.modeText}>
                  <Text style={styles.h3}>{m.title}</Text>
                  <Text style={styles.body}>{m.body}</Text>
                  <Text style={styles.modeApp}>{m.app}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.section} onLayout={track('apps')}>
          <Text style={styles.h2}>APPS TO DOWNLOAD</Text>
          <Text style={styles.sectionLede}>
            Junction plans the trip; these apps handle payment and unlocking. Install them and add a payment method before Games day so each hand-off is one tap.
          </Text>
          {APP_GROUPS.map((g) => (
            <View key={g.title} style={styles.appGroup}>
              <Text style={[styles.groupTitle, { color: g.color }]}>{g.title.toUpperCase()}</Text>
              <View style={styles.appGrid}>
                {g.apps.map((a) => (
                  <View key={a.name} style={styles.appRow}>
                    {a.crop ? (
                      <View style={[styles.logo, styles.logoCrop]}>
                        <Image source={a.logo} style={styles.logoCropped} resizeMode="contain" accessibilityLabel={`${a.name} logo`} />
                      </View>
                    ) : (
                      <Image source={a.logo} style={styles.logo} resizeMode="contain" accessibilityLabel={`${a.name} logo`} />
                    )}
                    <View style={styles.appText}>
                      <Text style={styles.appName}>{a.name}</Text>
                      <Text style={styles.body}>{a.body}</Text>
                    </View>
                  </View>
                ))}
              </View>
            </View>
          ))}
        </View>

        <View style={styles.cta}>
          <View style={styles.ctaText}>
            <Text style={styles.ctaTitle}>READY TO PLAN?</Text>
            <Text style={styles.ctaBody}>Pick a venue and see your options in seconds.</Text>
          </View>
          <Pressable onPress={() => router.push('/')} accessibilityRole="link" style={styles.ctaBtn}>
            <Text style={styles.ctaBtnText}>Open the map →</Text>
          </Pressable>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background },
  pageContent: { paddingBottom: 72 },
  container: {
    width: '100%',
    maxWidth: CONTENT_MAX_WIDTH,
    alignSelf: 'center',
    paddingHorizontal: spacing.md,
  },

  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, paddingTop: spacing.md },
  chip: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
  },
  chipText: { fontFamily: 'Barlow_600SemiBold', fontSize: 15, color: colors.foreground },

  intro: { paddingTop: 40, gap: spacing.md, maxWidth: 720 },
  eyebrow: { fontFamily: 'Barlow_700Bold', fontSize: 13, letterSpacing: 1.5, color: '#7E22CE' },
  h1: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 56, lineHeight: 54, color: colors.foreground },
  lede: { fontFamily: 'Barlow_400Regular', fontSize: 19, lineHeight: 28, color: colors.muted },

  section: { paddingTop: 72, gap: spacing.lg },
  h2: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 40, color: colors.foreground },
  sectionLede: { fontFamily: 'Barlow_400Regular', fontSize: 17, lineHeight: 25, color: colors.muted, maxWidth: 680, marginTop: -spacing.md },

  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  card: {
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: 22,
  },
  featureCard: { flexBasis: 260, gap: 10 },
  modeCard: { flexBasis: 320, flexDirection: 'row', gap: spacing.md },
  h3: { fontFamily: 'Barlow_700Bold', fontSize: 20, color: colors.foreground },
  body: { fontFamily: 'Barlow_400Regular', fontSize: 16, lineHeight: 24, color: colors.muted },

  modeIcon: { width: 48, height: 48, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  modeText: { flex: 1, gap: 6 },
  modeApp: { fontFamily: 'Barlow_600SemiBold', fontSize: 14, color: colors.foreground },

  appGroup: { gap: 12 },
  groupTitle: { fontFamily: 'Barlow_700Bold', fontSize: 14, letterSpacing: 1.5 },
  appGrid: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 32, rowGap: spacing.lg },
  appRow: { flexGrow: 1, flexBasis: 260, flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  logo: { width: 56, height: 56 },
  logoCrop: { overflow: 'hidden', borderRadius: 12 },
  logoCropped: { width: 86, height: 86, marginLeft: -15, marginTop: -15 },
  appText: { flex: 1, gap: 4, paddingTop: 4 },
  appName: { fontFamily: 'Barlow_700Bold', fontSize: 18, color: colors.foreground },

  cta: {
    marginTop: 72,
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    paddingVertical: 32,
    paddingHorizontal: spacing.lg,
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 20,
  },
  ctaText: { gap: 6 },
  ctaTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 34, color: '#FFFFFF' },
  ctaBody: { fontFamily: 'Barlow_400Regular', fontSize: 17, color: colors.mutedBg },
  ctaBtn: { minHeight: 48, justifyContent: 'center', paddingHorizontal: spacing.lg, borderRadius: radius.md, backgroundColor: brand.gold },
  ctaBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 17, color: colors.foreground },
});
