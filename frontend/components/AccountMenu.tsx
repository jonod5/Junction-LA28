// Global account avatar + dropdown — rendered once in the root layout (not
// per-screen, and not via the navigator's headerRight) so it's guaranteed to
// appear on every screen without duplicating it, and isn't subject to a
// navigator header's overflow clipping. Docked top:12,right:12 — the
// planner's own floating panel is top-left, and VenueDetailPanel is shifted
// down (top:64) to leave this corner free.
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

function initialsFrom(name: string | undefined, email: string | undefined): string {
  const source = (name || email || '?').trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

/** Always-visible entry point to the SP survey — anonymous by design, so
 * unlike everything else in this menu it must not be gated on sign-in or
 * even on Supabase being configured. */
function SurveyButton({ router }: { router: ReturnType<typeof useRouter> }) {
  return (
    <Pressable
      onPress={() => router.push('/survey')}
      accessibilityRole="button"
      accessibilityLabel="Take our travel survey"
      style={styles.surveyBtn}
    >
      <Feather name="clipboard" size={13} color={colors.primary} />
      <Text style={styles.surveyBtnText}>Survey</Text>
    </Pressable>
  );
}

export function AccountMenu() {
  const { user, account, loading, isConfigured, signInWithGoogle, signOut } = useAuth();
  const router = useRouter();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  // No Supabase project configured — the account half of this menu has
  // nothing to do, but the survey link still needs to show.
  if (!isConfigured || loading) {
    return (
      <View style={styles.wrap}>
        <SurveyButton router={router} />
      </View>
    );
  }

  if (!user) {
    return (
      <View style={styles.wrap}>
        <SurveyButton router={router} />
        <Pressable
          onPress={() => signInWithGoogle()}
          accessibilityRole="button"
          accessibilityLabel={t('common.signIn')}
          style={styles.signInBtn}
        >
          <Feather name="user" size={13} color={colors.primary} />
          <Text style={styles.signInText}>{t('common.signIn')}</Text>
        </Pressable>
      </View>
    );
  }

  // account.display_name is the editable, authoritative name (backend
  // mirror); Google's user_metadata.full_name is only a fallback for the
  // brief window before account has loaded.
  const displayName = account?.display_name
    ?? (user.user_metadata?.full_name as string | undefined)
    ?? user.email
    ?? '';
  const avatarUrl = user.user_metadata?.avatar_url as string | undefined;
  const initials = initialsFrom(displayName, user.email);

  return (
    <View style={styles.wrap}>
      <SurveyButton router={router} />
      <Pressable
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityLabel={t('account.menu.accountMenu')}
        style={styles.avatarBtn}
      >
        {avatarUrl ? (
          <Image source={{ uri: avatarUrl }} style={styles.avatarImg} />
        ) : (
          <View style={styles.avatarFallback}>
            <Text style={styles.avatarFallbackText}>{initials}</Text>
          </View>
        )}
      </Pressable>

      {open && (
        <>
          <Pressable style={styles.backdrop} onPress={() => setOpen(false)} />
          <View style={styles.menu}>
            <View style={styles.menuHeader}>
              {avatarUrl ? (
                <Image source={{ uri: avatarUrl }} style={styles.menuAvatarImg} />
              ) : (
                <View style={styles.menuAvatarFallback}>
                  <Text style={styles.avatarFallbackText}>{initials}</Text>
                </View>
              )}
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={styles.menuName} numberOfLines={1}>{displayName}</Text>
                <Text style={styles.menuEmail} numberOfLines={1}>{user.email}</Text>
              </View>
            </View>
            <View style={styles.menuDivider} />
            <Pressable
              onPress={() => { setOpen(false); router.push('/itineraries'); }}
              accessibilityRole="button"
              style={styles.menuItem}
            >
              <Feather name="bookmark" size={14} color={colors.foreground} />
              <Text style={styles.menuItemText}>{t('planner.myItineraries')}</Text>
            </Pressable>
            <Pressable
              onPress={() => { setOpen(false); router.push('/settings'); }}
              accessibilityRole="button"
              style={styles.menuItem}
            >
              <Feather name="settings" size={14} color={colors.foreground} />
              <Text style={styles.menuItemText}>{t('settings.title')}</Text>
            </Pressable>
            <View style={styles.menuDivider} />
            <Pressable
              onPress={() => { setOpen(false); signOut(); }}
              accessibilityRole="button"
              style={styles.menuItem}
            >
              <Feather name="log-out" size={14} color={colors.destructive} />
              <Text style={[styles.menuItemText, { color: colors.destructive }]}>{t('common.signOut')}</Text>
            </Pressable>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', top: 12, right: 12, zIndex: 200, flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  surveyBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: colors.surface, borderRadius: radius.full,
    paddingVertical: 8, paddingHorizontal: spacing.sm, ...shadow.sm,
  },
  surveyBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
  signInBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: colors.surface, borderRadius: radius.full,
    paddingVertical: 8, paddingHorizontal: spacing.sm, ...shadow.sm,
  },
  signInText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
  avatarBtn: { borderRadius: radius.full, ...shadow.sm },
  avatarImg: { width: 40, height: 40, borderRadius: 20, borderWidth: 2, borderColor: colors.surface },
  avatarFallback: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.primary,
    alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.surface,
  },
  avatarFallbackText: { fontFamily: 'Barlow_700Bold', fontSize: 14, color: colors.onPrimary },
  backdrop: { position: 'absolute', top: -2000, left: -2000, right: -2000, bottom: -2000, zIndex: 199 },
  menu: {
    position: 'absolute', top: 48, right: 0, width: 260,
    backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.xs,
    ...shadow.md, zIndex: 201,
  },
  menuHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, padding: spacing.sm },
  menuAvatarImg: { width: 36, height: 36, borderRadius: 18 },
  menuAvatarFallback: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: colors.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  menuName: { fontFamily: 'Barlow_600SemiBold', fontSize: 14, color: colors.foreground },
  menuEmail: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, marginTop: 1 },
  menuDivider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },
  menuItem: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: 10, paddingHorizontal: spacing.sm, borderRadius: radius.sm },
  menuItemText: { fontFamily: 'Barlow_500Medium', fontSize: 14, color: colors.foreground },
});
