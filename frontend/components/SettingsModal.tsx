// Settings window — opened from AccountMenu. Phase 1 ships just the Account
// section (profile + sign out); Travel preferences and Delete account are
// added once the /api/account backend exists.
import { Feather } from '@expo/vector-icons';
import React from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

interface Props {
  visible: boolean;
  onClose: () => void;
}

export function SettingsModal({ visible, onClose }: Props) {
  const { user, signOut } = useAuth();

  if (!visible || !user) return null;

  const displayName = (user.user_metadata?.full_name as string | undefined) ?? user.email ?? '';
  const avatarUrl = user.user_metadata?.avatar_url as string | undefined;

  return (
    <View style={styles.backdrop}>
      <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
      <View style={styles.card}>
        <View style={styles.header}>
          <Text style={styles.title}>Settings</Text>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close settings" hitSlop={8}>
            <Feather name="x" size={20} color={colors.muted} />
          </Pressable>
        </View>

        <ScrollView style={styles.body} contentContainerStyle={{ gap: spacing.lg }}>
          {/* ── Account ─────────────────────────────────────────────────── */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Account</Text>
            <View style={styles.profileRow}>
              {avatarUrl ? (
                <Image source={{ uri: avatarUrl }} style={styles.avatar} />
              ) : (
                <View style={[styles.avatar, styles.avatarFallback]}>
                  <Text style={styles.avatarFallbackText}>{displayName.slice(0, 2).toUpperCase()}</Text>
                </View>
              )}
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={styles.profileName} numberOfLines={1}>{displayName}</Text>
                <Text style={styles.profileEmail} numberOfLines={1}>{user.email}</Text>
              </View>
            </View>
            <Pressable onPress={() => { onClose(); signOut(); }} accessibilityRole="button" style={styles.secondaryBtn}>
              <Feather name="log-out" size={14} color={colors.primary} />
              <Text style={styles.secondaryBtnText}>Sign out</Text>
            </Pressable>
          </View>
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    position: 'absolute', top: -2000, left: -2000, right: -2000, bottom: -2000,
    backgroundColor: 'rgba(10,15,30,0.45)', alignItems: 'center', justifyContent: 'center', zIndex: 300,
  },
  card: {
    width: 420, maxHeight: 560, backgroundColor: colors.surface, borderRadius: radius.lg,
    padding: spacing.lg, ...shadow.md,
  },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm },
  title: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 22, color: colors.foreground, letterSpacing: 0.5 },
  body: { flexGrow: 0 },
  section: { gap: spacing.sm },
  sectionTitle: { fontFamily: 'Barlow_700Bold', fontSize: 12, color: colors.mutedFg, letterSpacing: 1, textTransform: 'uppercase' },
  profileRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  avatar: { width: 48, height: 48, borderRadius: 24 },
  avatarFallback: { backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  avatarFallbackText: { fontFamily: 'Barlow_700Bold', fontSize: 16, color: colors.onPrimary },
  profileName: { fontFamily: 'Barlow_600SemiBold', fontSize: 16, color: colors.foreground },
  profileEmail: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.muted, marginTop: 1 },
  secondaryBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, alignSelf: 'flex-start',
    borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.md,
    paddingVertical: 8, paddingHorizontal: spacing.md, minHeight: 40,
  },
  secondaryBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
});
