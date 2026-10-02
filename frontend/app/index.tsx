// Landing screen (the app's entry route): what Junction is, entry points to
// the planner and the SP survey, and the learn-more content below.
import { Feather } from '@expo/vector-icons';
import { useRouter, type Href } from 'expo-router';
import React, { useRef } from 'react';
import {
  Image,
  type LayoutChangeEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { BrandHeader, CONTENT_MAX_WIDTH } from '@/components/BrandHeader';
import { LearnMoreSections, type SectionKey } from '@/components/landing/LearnMoreSections';
import {
  BobArrow,
  CycleText,
  FadeIn,
  Float,
  Pulse,
  RevealProvider,
  useRevealHost,
} from '@/components/landing/motion';
import { brand, colors, radius, spacing } from '@/constants/theme';

const SCREENSHOT = require('@/assets/images/landing/app-screenshot.png');
const HUMAN_LAB = require('@/assets/images/landing/human-lab.png');

const EXAMPLE_TRIPS = [
  'LAX → SoFi Stadium',
  'Hotel → LA Memorial Coliseum',
  'Union Station → Dodger Stadium',
  'Santa Monica → Crypto.com Arena',
];

/** Height of the sticky BrandHeader plus breathing room, for jump targets. */
const JUMP_OFFSET = 64 + spacing.md;

type ActionCard = {
  /** A route to open, or 'learn' to scroll down to the learn-more content. */
  target: Href | 'learn';
  icon: React.ComponentProps<typeof Feather>['name'];
  title: string;
  body: string;
  cta: string;
  variant: 'primary' | 'secondary' | 'outline';
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

const LEARN_MORE: ActionCard = {
  target: 'learn',
  icon: 'info',
  title: 'How it works',
  body: 'Features, modes and apps to get.',
  cta: 'Learn more',
  variant: 'outline',
};

export default function LandingScreen() {
  const router = useRouter();
  const actions = [MAP, SURVEY, LEARN_MORE];
  const { width } = useWindowDimensions();
  const wide = width >= 860;

  const scrollRef = useRef<ScrollView>(null);
  const reveal = useRevealHost();
  const learnY = useRef(0);
  const sectionY = useRef<Record<SectionKey, number>>({ features: 0, modes: 0, apps: 0 });

  const scrollTo = (y: number) =>
    scrollRef.current?.scrollTo({ y: Math.max(y - JUMP_OFFSET, 0), animated: true });
  const jumpToSection = (key: SectionKey) => scrollTo(learnY.current + sectionY.current[key]);
  const openMap = () => router.push('/home');

  const onAction = (a: ActionCard) => {
    if (a.target === 'learn') scrollTo(learnY.current);
    else router.push(a.target);
  };

  return (
    <View style={styles.page}>
      <RevealProvider value={reveal.value}>
        <ScrollView
          ref={scrollRef}
          stickyHeaderIndices={[0]}
          onScroll={reveal.check}
          scrollEventThrottle={64}
          contentContainerStyle={styles.pageContent}
        >
          <BrandHeader />

          <View>
            <View style={[styles.container, styles.hero, wide && styles.heroWide]}>
              <View style={[styles.heroCopy, wide && styles.half]}>
                <FadeIn>
                  <Text style={[styles.h1, { fontSize: wide ? 76 : 48, lineHeight: wide ? 72 : 46 }]}>
                    EVERY VENUE.{'\n'}
                    <Text style={{ color: colors.primary }}>NO CAR NEEDED.</Text>
                  </Text>
                </FadeIn>
                <FadeIn delay={120}>
                  <Text style={styles.lede}>
                    Plan transit, bike, scooter and ride-hail trips to every LA28 venue.
                  </Text>
                </FadeIn>
                <FadeIn delay={240}>
                  <Pressable onPress={openMap} accessibilityRole="link" accessibilityLabel="Try a trip on the map" style={styles.tryPill}>
                    <Text style={styles.tryLabel}>Try</Text>
                    <CycleText items={EXAMPLE_TRIPS} style={styles.tryText} />
                    <View style={styles.roundBtn}>
                      <Feather name="arrow-right" size={18} color="#FFFFFF" />
                    </View>
                  </Pressable>
                </FadeIn>
              </View>

              <FadeIn delay={240} style={[styles.phoneWrap, wide && styles.half]}>
                <Pulse style={styles.glow} from={0.5} duration={1500}>
                  <View />
                </Pulse>
                <Float>
                  <View style={styles.phone}>
                    <Image
                      source={SCREENSHOT}
                      style={styles.screenshot}
                      resizeMode="cover"
                      accessibilityLabel="Junction on a phone: a route from LAX to SoFi Stadium drawn on the map, with ranked options below and Metro Micro marked best"
                    />
                  </View>
                </Float>
              </FadeIn>
            </View>

            <View style={[styles.container, styles.actions]}>
              {actions.map((a, i) => {
                const v = variantStyles[a.variant];
                return (
                  <FadeIn key={a.title} delay={360 + i * 120} style={styles.cardSlot}>
                    <Pressable
                      onPress={() => onAction(a)}
                      accessibilityRole="link"
                      style={(state) => [
                        styles.card,
                        v.card,
                        (state as { hovered?: boolean }).hovered && styles.cardHover,
                        state.pressed && styles.cardPressed,
                      ]}
                    >
                      <Feather name={a.icon} size={32} color={v.iconColor} />
                      <Text style={[styles.cardTitle, { color: v.titleColor }]}>{a.title}</Text>
                      <Text style={[styles.cardBody, { color: v.bodyColor }]}>{a.body}</Text>
                      <View style={styles.ctaRow}>
                        <Text style={[styles.cardCta, { color: v.ctaColor }]}>{a.cta}</Text>
                        {a.target === 'learn' ? <BobArrow style={[styles.cardCta, { color: v.ctaColor }]} /> : null}
                      </View>
                    </Pressable>
                  </FadeIn>
                );
              })}
            </View>
          </View>

          <View
            style={styles.learn}
            onLayout={(e: LayoutChangeEvent) => {
              learnY.current = e.nativeEvent.layout.y;
            }}
          >
            <LearnMoreSections
              onJump={jumpToSection}
              onSectionLayout={(key, y) => {
                sectionY.current[key] = y;
              }}
              onOpenMap={openMap}
            />
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
      </RevealProvider>
    </View>
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

  tryPill: {
    alignSelf: 'flex-start',
    width: 460,
    maxWidth: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 6,
    paddingRight: 6,
    paddingLeft: 18,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
  },
  tryLabel: { fontFamily: 'Barlow_400Regular', fontSize: 15, color: colors.muted },
  tryText: { fontFamily: 'Barlow_600SemiBold', fontSize: 16, color: colors.foreground },
  roundBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.full,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },

  phoneWrap: { alignItems: 'center', justifyContent: 'center' },
  glow: {
    position: 'absolute',
    width: 360,
    maxWidth: '100%',
    top: '8%',
    bottom: '8%',
    borderRadius: radius.full,
    backgroundColor: 'rgba(99,102,241,0.22)',
    // Soft halo on web; native falls back to the flat tint.
    ...({ filter: 'blur(28px)' } as object),
  },
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
  cardSlot: { flexGrow: 1, flexBasis: 240 },
  card: {
    flex: 1,
    minHeight: 200,
    padding: spacing.lg,
    borderRadius: radius.lg,
    gap: 14,
  },
  cardHover: {
    transform: [{ translateY: -2 }],
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 28,
  },
  cardPressed: { opacity: 0.85 },
  ctaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  cardTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 30, textTransform: 'uppercase' },
  cardBody: { fontFamily: 'Barlow_400Regular', fontSize: 16, lineHeight: 23, flexGrow: 1 },
  cardCta: { fontFamily: 'Barlow_600SemiBold', fontSize: 15 },

  learn: { backgroundColor: '#F7FAFF', borderTopWidth: 1, borderTopColor: colors.border },

  footer: {
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
