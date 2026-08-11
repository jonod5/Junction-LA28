// My Itineraries — web-only for now (uses window.prompt/confirm for the
// lightweight rename/tag-edit/delete-confirm flows rather than building
// custom dialogs for a secondary account-management page). Native falls
// back to a simple "not available yet" message.
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';
import { api, type Itinerary } from '@/lib/api';
import i18next from '@/lib/i18n';
import { useTrip } from '@/lib/store';

function formatDate(d: string | null, t: (key: string) => string): string {
  if (!d) return t('itineraries.noDate');
  return new Date(`${d}T00:00:00`).toLocaleDateString(i18next.language, {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function ItinerariesScreen() {
  const { user, loading: authLoading, isConfigured, signInWithGoogle } = useAuth();
  const { hydrateFromSnapshot } = useTrip();
  const router = useRouter();
  const { t } = useTranslation();

  const [upcoming, setUpcoming] = useState<Itinerary[]>([]);
  const [past, setPast] = useState<Itinerary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const [up, pa] = await Promise.all([
        api.listItineraries({ status: 'upcoming', tag: tagFilter ?? undefined, sort: 'trip_date', order: 'asc', limit: 100 }),
        api.listItineraries({ status: 'past', tag: tagFilter ?? undefined, sort: 'trip_date', order: 'desc', limit: 100 }),
      ]);
      setUpcoming(up.items);
      setPast(pa.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('itineraries.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [user, tagFilter, t]);

  useEffect(() => {
    load();
  }, [load]);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    [...upcoming, ...past].forEach((it) => it.tags.forEach((tag) => s.add(tag)));
    return [...s].sort();
  }, [upcoming, past]);

  const openItinerary = async (it: Itinerary) => {
    setBusyId(it.id);
    const ok = await hydrateFromSnapshot(it.saved_plan);
    setBusyId(null);
    if (ok) router.replace('/');
  };

  const togglePin = async (it: Itinerary) => {
    setBusyId(it.id);
    try {
      await api.updateItinerary(it.id, { is_pinned: !it.is_pinned });
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const rename = async (it: Itinerary) => {
    const next = window.prompt(t('itineraries.prompts.renameTitle'), it.name);
    if (!next || !next.trim() || next.trim() === it.name) return;
    setBusyId(it.id);
    try {
      await api.updateItinerary(it.id, { name: next.trim() });
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const editTags = async (it: Itinerary) => {
    const next = window.prompt(t('itineraries.prompts.tagsTitle'), it.tags.join(', '));
    if (next === null) return;
    setBusyId(it.id);
    try {
      await api.updateItinerary(it.id, { tags: next.split(',').map((tag) => tag.trim()).filter(Boolean) });
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (it: Itinerary) => {
    if (!window.confirm(t('itineraries.prompts.deleteConfirm', { name: it.name }))) return;
    setBusyId(it.id);
    try {
      await api.deleteItinerary(it.id);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  if (Platform.OS !== 'web') {
    return (
      <View style={styles.centered}>
        <Text style={styles.hint}>{t('itineraries.nativeUnavailable')}</Text>
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
        <Feather name="bookmark" size={32} color={colors.mutedFg} />
        <Text style={styles.title}>{t('itineraries.signInPrompt.title')}</Text>
        <Text style={styles.hint}>{t('itineraries.signInPrompt.hint')}</Text>
        {isConfigured ? (
          <Pressable onPress={() => signInWithGoogle()} accessibilityRole="button" style={styles.primaryBtn}>
            <Text style={styles.primaryBtnText}>{t('common.signInWithGoogle')}</Text>
          </Pressable>
        ) : (
          <Text style={styles.hint}>{t('itineraries.signInPrompt.notConfigured')}</Text>
        )}
      </View>
    );
  }

  const isEmpty = !loading && upcoming.length === 0 && past.length === 0;

  return (
    <ScrollView style={styles.wrapper} contentContainerStyle={styles.content}>
      {error && <Text style={styles.errorText}>{error}</Text>}

      {allTags.length > 0 && (
        <View style={styles.tagRow}>
          <Pressable onPress={() => setTagFilter(null)} style={[styles.tagChip, !tagFilter && styles.tagChipActive]}>
            <Text style={[styles.tagChipText, !tagFilter && styles.tagChipTextActive]}>{t('itineraries.allTag')}</Text>
          </Pressable>
          {allTags.map((tag) => (
            <Pressable key={tag} onPress={() => setTagFilter(tag)} style={[styles.tagChip, tagFilter === tag && styles.tagChipActive]}>
              <Text style={[styles.tagChipText, tagFilter === tag && styles.tagChipTextActive]}>{tag}</Text>
            </Pressable>
          ))}
        </View>
      )}

      {loading && <ActivityIndicator color={colors.primary} style={{ marginVertical: spacing.lg }} />}

      {isEmpty && (
        <View style={styles.centered}>
          <Feather name="map" size={32} color={colors.mutedFg} />
          <Text style={styles.title}>{t('itineraries.empty.title')}</Text>
          <Text style={styles.hint}>{t('itineraries.empty.hint')}</Text>
        </View>
      )}

      {upcoming.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{t('itineraries.upcoming')}</Text>
          {upcoming.map((it) => (
            <ItineraryCard
              key={it.id}
              itinerary={it}
              busy={busyId === it.id}
              onOpen={() => openItinerary(it)}
              onPin={() => togglePin(it)}
              onRename={() => rename(it)}
              onEditTags={() => editTags(it)}
              onDelete={() => remove(it)}
            />
          ))}
        </View>
      )}

      {past.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{t('itineraries.past')}</Text>
          {past.map((it) => (
            <ItineraryCard
              key={it.id}
              itinerary={it}
              busy={busyId === it.id}
              onOpen={() => openItinerary(it)}
              onPin={() => togglePin(it)}
              onRename={() => rename(it)}
              onEditTags={() => editTags(it)}
              onDelete={() => remove(it)}
            />
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function ItineraryCard({ itinerary, busy, onOpen, onPin, onRename, onEditTags, onDelete }: {
  itinerary: Itinerary;
  busy: boolean;
  onOpen: () => void;
  onPin: () => void;
  onRename: () => void;
  onEditTags: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <View style={styles.card}>
      <Pressable
        onPress={onOpen}
        disabled={busy}
        style={styles.cardBody}
        accessibilityRole="button"
        accessibilityLabel={t('itineraries.actions.open', { name: itinerary.name })}
      >
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            {itinerary.is_pinned && <Feather name="star" size={13} color={colors.gold} />}
            <Text style={styles.cardTitle} numberOfLines={1}>{itinerary.name}</Text>
          </View>
          <Text style={styles.cardMeta}>
            {formatDate(itinerary.trip_date, t)} · {t('itineraries.stops', { count: itinerary.saved_plan.stops.length })}
          </Text>
          {itinerary.tags.length > 0 && (
            <Text style={styles.cardTags} numberOfLines={1}>{itinerary.tags.join(' · ')}</Text>
          )}
        </View>
        {busy && <ActivityIndicator color={colors.primary} size="small" />}
      </Pressable>
      <View style={styles.cardActions}>
        <Pressable onPress={onPin} disabled={busy} hitSlop={8} accessibilityLabel={itinerary.is_pinned ? t('itineraries.actions.unpin') : t('itineraries.actions.pin')}>
          <Feather name="star" size={15} color={itinerary.is_pinned ? colors.gold : colors.mutedFg} />
        </Pressable>
        <Pressable onPress={onRename} disabled={busy} hitSlop={8} accessibilityLabel={t('itineraries.actions.rename')}>
          <Feather name="edit-2" size={15} color={colors.mutedFg} />
        </Pressable>
        <Pressable onPress={onEditTags} disabled={busy} hitSlop={8} accessibilityLabel={t('itineraries.actions.editTags')}>
          <Feather name="tag" size={15} color={colors.mutedFg} />
        </Pressable>
        <Pressable onPress={onDelete} disabled={busy} hitSlop={8} accessibilityLabel={t('itineraries.actions.delete')}>
          <Feather name="trash-2" size={15} color={colors.destructive} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, gap: spacing.md, maxWidth: 640, width: '100%', alignSelf: 'center' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.sm, padding: spacing.xl },
  title: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 20, color: colors.foreground, textAlign: 'center' },
  hint: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.muted, textAlign: 'center', lineHeight: 19 },
  errorText: { fontFamily: 'Barlow_400Regular', fontSize: 13, color: colors.destructive },
  primaryBtn: { backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.sm, paddingHorizontal: spacing.lg, marginTop: spacing.xs },
  primaryBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 14, color: colors.onPrimary },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  tagChip: { paddingHorizontal: spacing.sm, paddingVertical: 6, borderRadius: radius.full, borderWidth: 1.5, borderColor: colors.border },
  tagChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  tagChipText: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.muted },
  tagChipTextActive: { color: colors.onPrimary },
  section: { gap: spacing.sm },
  sectionTitle: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 18, color: colors.foreground, letterSpacing: 0.5 },
  card: { backgroundColor: colors.surface, borderRadius: radius.md, ...shadow.sm, overflow: 'hidden' },
  cardBody: { flexDirection: 'row', alignItems: 'center', padding: spacing.sm, gap: spacing.sm },
  cardTitle: { fontFamily: 'Barlow_600SemiBold', fontSize: 15, color: colors.foreground, flexShrink: 1 },
  cardMeta: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.muted, marginTop: 2 },
  cardTags: { fontFamily: 'Barlow_400Regular', fontSize: 11, color: colors.mutedFg, marginTop: 2 },
  cardActions: { flexDirection: 'row', gap: spacing.md, paddingHorizontal: spacing.sm, paddingBottom: spacing.sm },
});
