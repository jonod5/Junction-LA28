// Settings — full page (was a popup; moved here so it has room to breathe
// and gets its own URL/back button like My Itineraries). Web-only for now,
// same as itineraries.tsx, for the same reason: native fallback screens are
// legacy and this feature never shipped there.
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ModePreferencesChecklist } from '@/components/ModePreferencesChecklist';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { api, type RouteMode } from '@/lib/api';
import { useAuth } from '@/lib/auth';

export default function SettingsScreen() {
  const { user, loading: authLoading, signOut } = useAuth();
  const router = useRouter();

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const [defaultModes, setDefaultModes] = useState<RouteMode[]>([]);
  const [prefsLoading, setPrefsLoading] = useState(false);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsError, setPrefsError] = useState<string | null>(null);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const displayName = (user?.user_metadata?.full_name as string | undefined) ?? user?.email ?? '';
  const avatarUrl = user?.user_metadata?.avatar_url as string | undefined;

  useEffect(() => {
    if (!user) return;
    setNameDraft(displayName);
    setPrefsLoading(true);
    setPrefsError(null);
    api.getAccount()
      .then((acct) => setDefaultModes(acct.preferences?.default_modes ?? []))
      .catch((e: unknown) => setPrefsError(e instanceof Error ? e.message : 'Could not load preferences'))
      .finally(() => setPrefsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const handleSaveName = async () => {
    const trimmed = nameDraft.trim();
    if (!trimmed) return;
    setNameSaving(true);
    setNameError(null);
    try {
      await api.updateAccount({ display_name: trimmed });
      setEditingName(false);
    } catch (e: unknown) {
      setNameError(e instanceof Error ? e.message : 'Could not save name');
    } finally {
      setNameSaving(false);
    }
  };

  const handleChangeModes = async (modes: RouteMode[]) => {
    const previous = defaultModes;
    setDefaultModes(modes);
    setPrefsSaving(true);
    setPrefsError(null);
    try {
      await api.updateAccount({ default_modes: modes });
    } catch (e: unknown) {
      setDefaultModes(previous); // rollback on failure
      setPrefsError(e instanceof Error ? e.message : 'Could not save preferences');
    } finally {
      setPrefsSaving(false);
    }
  };

  const deleteConfirmed = deleteConfirmText.trim().toUpperCase() === 'DELETE';

  const handleDeleteAccount = async () => {
    if (!deleteConfirmed) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteAccount();
      await signOut();
      router.replace('/');
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Could not delete account — please try again.');
      setDeleting(false);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    router.replace('/');
  };

  if (Platform.OS !== 'web') {
    return (
      <View style={styles.centered}>
        <Text style={styles.hint}>Settings is available on the web app for now.</Text>
      </View>
    );
  }

  if (authLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (!user) {
    return (
      <View style={styles.centered}>
        <Feather name="settings" size={32} color={colors.mutedFg} />
        <Text style={styles.title}>Sign in to manage your account</Text>
        <Text style={styles.hint}>Settings are only available once you're signed in.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.wrapper} contentContainerStyle={styles.content}>
      {/* ── Account ─────────────────────────────────────────────────────── */}
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
            {editingName ? (
              <TextInput
                value={nameDraft}
                onChangeText={setNameDraft}
                style={styles.nameInput}
                autoFocus
                accessibilityLabel="Display name"
              />
            ) : (
              <Text style={styles.profileName} numberOfLines={1}>{displayName}</Text>
            )}
            <Text style={styles.profileEmail} numberOfLines={1}>{user.email}</Text>
          </View>
          {editingName ? (
            <Pressable onPress={handleSaveName} disabled={nameSaving} accessibilityRole="button" accessibilityLabel="Save name" hitSlop={8}>
              {nameSaving ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : (
                <Feather name="check" size={18} color={colors.primary} />
              )}
            </Pressable>
          ) : (
            <Pressable onPress={() => setEditingName(true)} accessibilityRole="button" accessibilityLabel="Edit display name" hitSlop={8}>
              <Feather name="edit-2" size={16} color={colors.muted} />
            </Pressable>
          )}
        </View>
        {nameError && <Text style={styles.errorText}>{nameError}</Text>}

        <Pressable onPress={handleSignOut} accessibilityRole="button" style={styles.secondaryBtn}>
          <Feather name="log-out" size={14} color={colors.primary} />
          <Text style={styles.secondaryBtnText}>Sign out</Text>
        </Pressable>
      </View>

      {/* ── Travel preferences ──────────────────────────────────────────── */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Travel preferences</Text>
        <Text style={styles.sectionHint}>
          Default ways you're open to traveling — pre-fills a new trip's onboarding.
        </Text>
        {prefsLoading ? (
          <ActivityIndicator color={colors.primary} size="small" style={{ alignSelf: 'flex-start' }} />
        ) : (
          <ModePreferencesChecklist selected={defaultModes} onChange={handleChangeModes} />
        )}
        {prefsSaving && <Text style={styles.sectionHint}>Saving…</Text>}
        {prefsError && <Text style={styles.errorText}>{prefsError}</Text>}
      </View>

      {/* ── Data & privacy ──────────────────────────────────────────────── */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Data &amp; privacy</Text>
        <Pressable onPress={() => router.push('/itineraries')} accessibilityRole="button" style={styles.linkRow}>
          <Feather name="bookmark" size={14} color={colors.foreground} />
          <Text style={styles.linkText}>Manage saved itineraries</Text>
          <Feather name="chevron-right" size={14} color={colors.mutedFg} />
        </Pressable>
        {/* Placeholder URLs — real ones needed before App Store submission. */}
        <Pressable onPress={() => Linking.openURL('https://example.com/privacy')} accessibilityRole="button" style={styles.linkRow}>
          <Feather name="shield" size={14} color={colors.foreground} />
          <Text style={styles.linkText}>Privacy Policy</Text>
          <Feather name="external-link" size={12} color={colors.mutedFg} />
        </Pressable>
        <Pressable onPress={() => Linking.openURL('https://example.com/terms')} accessibilityRole="button" style={[styles.linkRow, { borderBottomWidth: 0 }]}>
          <Feather name="file-text" size={14} color={colors.foreground} />
          <Text style={styles.linkText}>Terms of Service</Text>
          <Feather name="external-link" size={12} color={colors.mutedFg} />
        </Pressable>
      </View>

      {/* ── Danger zone ─────────────────────────────────────────────────── */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.destructive }]}>Danger zone</Text>
        {!deleteOpen ? (
          <Pressable onPress={() => setDeleteOpen(true)} accessibilityRole="button" style={styles.dangerBtn}>
            <Feather name="trash-2" size={14} color={colors.destructive} />
            <Text style={styles.dangerBtnText}>Delete account</Text>
          </Pressable>
        ) : (
          <View style={{ gap: spacing.xs }}>
            <Text style={styles.sectionHint}>
              This permanently deletes your account and every saved itinerary. This can't be undone.
              Type DELETE to confirm.
            </Text>
            <TextInput
              value={deleteConfirmText}
              onChangeText={setDeleteConfirmText}
              placeholder="DELETE"
              placeholderTextColor={colors.mutedFg}
              style={styles.input}
              autoCapitalize="characters"
              accessibilityLabel="Type DELETE to confirm account deletion"
            />
            {deleteError && <Text style={styles.errorText}>{deleteError}</Text>}
            <View style={{ flexDirection: 'row', gap: spacing.sm }}>
              <Pressable
                onPress={() => { setDeleteOpen(false); setDeleteConfirmText(''); }}
                disabled={deleting}
                style={styles.secondaryBtn}
              >
                <Text style={styles.secondaryBtnText}>Cancel</Text>
              </Pressable>
              <Pressable
                onPress={handleDeleteAccount}
                disabled={deleting || !deleteConfirmed}
                style={[styles.dangerBtnFilled, (deleting || !deleteConfirmed) && styles.dangerBtnFilledDisabled]}
              >
                {deleting ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={styles.dangerBtnFilledText}>Permanently delete</Text>
                )}
              </Pressable>
            </View>
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, gap: spacing.lg, maxWidth: 640, width: '100%', alignSelf: 'center' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.sm, padding: spacing.xl },
  title: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 20, color: colors.foreground, textAlign: 'center' },
  hint: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.muted, textAlign: 'center', lineHeight: 19 },
  section: { gap: spacing.sm, backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.md, ...shadow.sm },
  sectionTitle: { fontFamily: 'Barlow_700Bold', fontSize: 12, color: colors.mutedFg, letterSpacing: 1, textTransform: 'uppercase' },
  sectionHint: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, lineHeight: 17 },
  profileRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  avatar: { width: 48, height: 48, borderRadius: 24 },
  avatarFallback: { backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  avatarFallbackText: { fontFamily: 'Barlow_700Bold', fontSize: 16, color: colors.onPrimary },
  profileName: { fontFamily: 'Barlow_600SemiBold', fontSize: 16, color: colors.foreground },
  profileEmail: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.muted, marginTop: 1 },
  nameInput: {
    fontFamily: 'Barlow_600SemiBold', fontSize: 15, color: colors.foreground,
    backgroundColor: colors.mutedBg, borderRadius: radius.sm, paddingHorizontal: spacing.xs, paddingVertical: 4,
  },
  errorText: { fontFamily: 'Barlow_400Regular', fontSize: 11, color: colors.destructive },
  input: {
    fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.foreground,
    backgroundColor: colors.mutedBg, borderRadius: radius.sm,
    paddingHorizontal: spacing.sm, paddingVertical: 8, minHeight: 40,
  },
  secondaryBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, alignSelf: 'flex-start',
    borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.md,
    paddingVertical: 8, paddingHorizontal: spacing.md, minHeight: 40,
  },
  secondaryBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
  linkRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  linkText: { flex: 1, fontFamily: 'Barlow_500Medium', fontSize: 14, color: colors.foreground },
  dangerBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, alignSelf: 'flex-start',
    borderWidth: 1.5, borderColor: colors.destructive, borderRadius: radius.md,
    paddingVertical: 8, paddingHorizontal: spacing.md, minHeight: 40,
  },
  dangerBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.destructive },
  dangerBtnFilled: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.destructive, borderRadius: radius.md, paddingVertical: 8, minHeight: 40,
  },
  dangerBtnFilledDisabled: { opacity: 0.4 },
  dangerBtnFilledText: { fontFamily: 'Barlow_700Bold', fontSize: 13, color: '#fff' },
});
