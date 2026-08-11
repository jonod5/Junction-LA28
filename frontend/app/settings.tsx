// Settings — full page (was a popup; moved here so it has room to breathe
// and gets its own URL/back button like My Itineraries). Web-only for now,
// same as itineraries.tsx, for the same reason: native fallback screens are
// legacy and this feature never shipped there.
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
import {
  changeLanguage,
  LANGUAGE_LABELS,
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
} from '@/lib/i18n';

export default function SettingsScreen() {
  const { user, account, loading: authLoading, signOut, refreshAccount } = useAuth();
  const router = useRouter();
  const { t, i18n } = useTranslation();

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const [defaultModes, setDefaultModes] = useState<RouteMode[]>([]);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsError, setPrefsError] = useState<string | null>(null);

  const [languageSaving, setLanguageSaving] = useState(false);
  const [languageError, setLanguageError] = useState<string | null>(null);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // account.display_name is the editable, authoritative name (backend
  // mirror) — Google's user_metadata.full_name is read-only from this app,
  // so it's only used as a fallback before account has loaded.
  const displayName = account?.display_name
    ?? (user?.user_metadata?.full_name as string | undefined)
    ?? user?.email
    ?? '';
  const avatarUrl = user?.user_metadata?.avatar_url as string | undefined;
  const prefsLoading = !account;

  // Seeds from the shared account cache — not a local fetch — so this page
  // reflects a change made elsewhere (or a moment ago, on this same page)
  // without going stale.
  useEffect(() => {
    if (!account) return;
    setNameDraft(account.display_name ?? '');
    setDefaultModes(account.preferences?.default_modes ?? []);
  }, [account]);

  const handleSaveName = async () => {
    const trimmed = nameDraft.trim();
    if (!trimmed) return;
    setNameSaving(true);
    setNameError(null);
    try {
      await api.updateAccount({ display_name: trimmed });
      await refreshAccount();
      setEditingName(false);
    } catch (e: unknown) {
      setNameError(e instanceof Error ? e.message : t('settings.account.nameSaveFailed'));
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
      await refreshAccount();
    } catch (e: unknown) {
      setDefaultModes(previous); // rollback on failure
      setPrefsError(e instanceof Error ? e.message : t('settings.travelPreferences.saveFailed'));
    } finally {
      setPrefsSaving(false);
    }
  };

  // Switches immediately (re-renders the whole app) and always updates the
  // local cache via changeLanguage() — anonymous users stop there. Signed-in
  // users additionally get it written to their account so it follows them
  // across devices.
  const handleChangeLanguage = async (lang: SupportedLanguage) => {
    changeLanguage(lang);
    if (!user) return;
    setLanguageSaving(true);
    setLanguageError(null);
    try {
      await api.updateAccount({ language: lang });
      await refreshAccount();
    } catch (e: unknown) {
      setLanguageError(e instanceof Error ? e.message : t('settings.language.saveFailed'));
    } finally {
      setLanguageSaving(false);
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
      setDeleteError(e instanceof Error ? e.message : t('settings.dangerZone.deleteFailed'));
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
        <Text style={styles.hint}>{t('settings.nativeUnavailable')}</Text>
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

  return (
    <ScrollView style={styles.wrapper} contentContainerStyle={styles.content}>
      {!user && (
        <View style={styles.section}>
          <Feather name="settings" size={24} color={colors.mutedFg} />
          <Text style={styles.title}>{t('settings.signInPrompt.title')}</Text>
          <Text style={styles.hint}>{t('settings.signInPrompt.hint')}</Text>
        </View>
      )}

      {/* ── Language ─────────────────────────────────────────────────────── */}
      {/* Available signed out too — the choice persists locally either way,
          and syncs to the account once signed in (see handleChangeLanguage). */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('settings.language.sectionTitle')}</Text>
        <Text style={styles.sectionHint}>{t('settings.language.hint')}</Text>
        <View style={styles.languageRow}>
          {SUPPORTED_LANGUAGES.map((lang) => {
            const active = i18n.language === lang;
            return (
              <Pressable
                key={lang}
                onPress={() => handleChangeLanguage(lang)}
                disabled={languageSaving}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                style={[styles.languageChip, active && styles.languageChipActive]}
              >
                <Text style={[styles.languageChipText, active && styles.languageChipTextActive]}>
                  {LANGUAGE_LABELS[lang]}
                </Text>
              </Pressable>
            );
          })}
        </View>
        {languageError && <Text style={styles.errorText}>{languageError}</Text>}
      </View>

      {user && (
        <>
          {/* ── Account ─────────────────────────────────────────────────── */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>{t('settings.account.sectionTitle')}</Text>
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
                    accessibilityLabel={t('settings.account.editName')}
                  />
                ) : (
                  <Text style={styles.profileName} numberOfLines={1}>{displayName}</Text>
                )}
                <Text style={styles.profileEmail} numberOfLines={1}>{user.email}</Text>
              </View>
              {editingName ? (
                <Pressable onPress={handleSaveName} disabled={nameSaving} accessibilityRole="button" accessibilityLabel={t('settings.account.saveName')} hitSlop={8}>
                  {nameSaving ? (
                    <ActivityIndicator size="small" color={colors.primary} />
                  ) : (
                    <Feather name="check" size={18} color={colors.primary} />
                  )}
                </Pressable>
              ) : (
                <Pressable onPress={() => setEditingName(true)} accessibilityRole="button" accessibilityLabel={t('settings.account.editName')} hitSlop={8}>
                  <Feather name="edit-2" size={16} color={colors.muted} />
                </Pressable>
              )}
            </View>
            {nameError && <Text style={styles.errorText}>{nameError}</Text>}

            <Pressable onPress={handleSignOut} accessibilityRole="button" style={styles.secondaryBtn}>
              <Feather name="log-out" size={14} color={colors.primary} />
              <Text style={styles.secondaryBtnText}>{t('common.signOut')}</Text>
            </Pressable>
          </View>

          {/* ── Travel preferences ──────────────────────────────────────── */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>{t('settings.travelPreferences.sectionTitle')}</Text>
            <Text style={styles.sectionHint}>{t('settings.travelPreferences.hint')}</Text>
            {prefsLoading ? (
              <ActivityIndicator color={colors.primary} size="small" style={{ alignSelf: 'flex-start' }} />
            ) : (
              <ModePreferencesChecklist selected={defaultModes} onChange={handleChangeModes} />
            )}
            {prefsSaving && <Text style={styles.sectionHint}>{t('settings.travelPreferences.saving')}</Text>}
            {prefsError && <Text style={styles.errorText}>{prefsError}</Text>}
          </View>

          {/* ── Data & privacy ─────────────────────────────────────────── */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>{t('settings.dataPrivacy.sectionTitle')}</Text>
            <Pressable onPress={() => router.push('/itineraries')} accessibilityRole="button" style={styles.linkRow}>
              <Feather name="bookmark" size={14} color={colors.foreground} />
              <Text style={styles.linkText}>{t('settings.dataPrivacy.manageItineraries')}</Text>
              <Feather name="chevron-right" size={14} color={colors.mutedFg} />
            </Pressable>
            {/* Placeholder URLs — real ones needed before App Store submission. */}
            <Pressable onPress={() => Linking.openURL('https://example.com/privacy')} accessibilityRole="button" style={styles.linkRow}>
              <Feather name="shield" size={14} color={colors.foreground} />
              <Text style={styles.linkText}>{t('settings.dataPrivacy.privacyPolicy')}</Text>
              <Feather name="external-link" size={12} color={colors.mutedFg} />
            </Pressable>
            <Pressable onPress={() => Linking.openURL('https://example.com/terms')} accessibilityRole="button" style={[styles.linkRow, { borderBottomWidth: 0 }]}>
              <Feather name="file-text" size={14} color={colors.foreground} />
              <Text style={styles.linkText}>{t('settings.dataPrivacy.termsOfService')}</Text>
              <Feather name="external-link" size={12} color={colors.mutedFg} />
            </Pressable>
          </View>

          {/* ── Danger zone ───────────────────────────────────────────── */}
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.destructive }]}>{t('settings.dangerZone.sectionTitle')}</Text>
            {!deleteOpen ? (
              <Pressable onPress={() => setDeleteOpen(true)} accessibilityRole="button" style={styles.dangerBtn}>
                <Feather name="trash-2" size={14} color={colors.destructive} />
                <Text style={styles.dangerBtnText}>{t('settings.dangerZone.deleteAccount')}</Text>
              </Pressable>
            ) : (
              <View style={{ gap: spacing.xs }}>
                <Text style={styles.sectionHint}>{t('settings.dangerZone.deleteWarning')}</Text>
                <TextInput
                  value={deleteConfirmText}
                  onChangeText={setDeleteConfirmText}
                  placeholder={t('settings.dangerZone.deleteConfirmPlaceholder')}
                  placeholderTextColor={colors.mutedFg}
                  style={styles.input}
                  autoCapitalize="characters"
                  accessibilityLabel={t('settings.dangerZone.deleteWarning')}
                />
                {deleteError && <Text style={styles.errorText}>{deleteError}</Text>}
                <View style={{ flexDirection: 'row', gap: spacing.sm }}>
                  <Pressable
                    onPress={() => { setDeleteOpen(false); setDeleteConfirmText(''); }}
                    disabled={deleting}
                    style={styles.secondaryBtn}
                  >
                    <Text style={styles.secondaryBtnText}>{t('common.cancel')}</Text>
                  </Pressable>
                  <Pressable
                    onPress={handleDeleteAccount}
                    disabled={deleting || !deleteConfirmed}
                    style={[styles.dangerBtnFilled, (deleting || !deleteConfirmed) && styles.dangerBtnFilledDisabled]}
                  >
                    {deleting ? (
                      <ActivityIndicator color="#fff" size="small" />
                    ) : (
                      <Text style={styles.dangerBtnFilledText}>{t('settings.dangerZone.deletePermanently')}</Text>
                    )}
                  </Pressable>
                </View>
              </View>
            )}
          </View>
        </>
      )}
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
  languageRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  languageChip: {
    paddingHorizontal: spacing.sm, paddingVertical: 8, borderRadius: radius.full,
    borderWidth: 1.5, borderColor: colors.border, minHeight: 36,
  },
  languageChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  languageChipText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.foreground },
  languageChipTextActive: { color: colors.onPrimary },
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
