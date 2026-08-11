import { Feather } from '@expo/vector-icons';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { colors, radius, shadow, spacing } from '@/constants/theme';

interface Props {
  visible: boolean;
  initialName: string;
  initialTripDate: string | null;
  initialTags: string[];
  saving: boolean;
  errorText?: string | null;
  onCancel: () => void;
  onSave: (name: string, tripDate: string | null, tags: string[]) => void;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Name + trip date + tags prompt shown when saving the current plan as an
 *  itinerary — also reused to resume a save after a sign-in redirect, in
 *  which case `initial*` props come from the stashed pending save. */
export function SaveItineraryDialog({
  visible, initialName, initialTripDate, initialTags, saving, errorText, onCancel, onSave,
}: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState(initialName);
  const [tripDate, setTripDate] = useState(initialTripDate ?? '');
  const [tagsText, setTagsText] = useState(initialTags.join(', '));

  useEffect(() => {
    if (visible) {
      setName(initialName);
      setTripDate(initialTripDate ?? '');
      setTagsText(initialTags.join(', '));
    }
  }, [visible, initialName, initialTripDate, initialTags]);

  if (!visible) return null;

  const trimmedDate = tripDate.trim();
  const dateValid = trimmedDate === '' || DATE_RE.test(trimmedDate);
  const canSave = name.trim().length > 0 && dateValid && !saving;

  const handleSave = () => {
    if (!canSave) return;
    const tags = tagsText.split(',').map((t) => t.trim()).filter(Boolean);
    onSave(name.trim(), trimmedDate || null, tags);
  };

  return (
    <View style={styles.backdrop}>
      <View style={styles.card}>
        <Text style={styles.title}>{t('saveDialog.title')}</Text>

        <Text style={styles.label}>{t('saveDialog.nameLabel')}</Text>
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder={t('saveDialog.namePlaceholder')}
          placeholderTextColor={colors.mutedFg}
          style={styles.input}
          accessibilityLabel={t('saveDialog.nameLabel')}
        />

        <Text style={styles.label}>{t('saveDialog.dateLabel')}</Text>
        {Platform.OS === 'web' ? (
          // Native browser date picker — a real calendar dropdown, and
          // e.target.value is already YYYY-MM-DD so no format validation
          // is needed on this path.
          <input
            type="date"
            value={tripDate}
            onChange={(e) => setTripDate(e.target.value)}
            aria-label={t('saveDialog.dateLabel')}
            style={webDateInputStyle}
          />
        ) : (
          <TextInput
            value={tripDate}
            onChangeText={setTripDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={colors.mutedFg}
            style={styles.input}
            accessibilityLabel={t('saveDialog.dateLabel')}
          />
        )}
        {!dateValid && <Text style={styles.errorText}>{t('saveDialog.dateFormatHint')}</Text>}

        <Text style={styles.label}>{t('saveDialog.tagsLabel')}</Text>
        <TextInput
          value={tagsText}
          onChangeText={setTagsText}
          placeholder={t('saveDialog.tagsPlaceholder')}
          placeholderTextColor={colors.mutedFg}
          style={styles.input}
          accessibilityLabel={t('saveDialog.tagsLabel')}
        />

        {errorText && <Text style={styles.errorText}>{errorText}</Text>}

        <View style={styles.actions}>
          <Pressable onPress={onCancel} disabled={saving} style={styles.secondaryBtn}>
            <Text style={styles.secondaryBtnText}>{t('common.cancel')}</Text>
          </Pressable>
          <Pressable
            onPress={handleSave}
            disabled={!canSave}
            accessibilityRole="button"
            style={[styles.primaryBtn, !canSave && styles.primaryBtnDisabled]}
          >
            {saving ? (
              <ActivityIndicator color={colors.onPrimary} size="small" />
            ) : (
              <>
                <Feather name="bookmark" size={14} color={colors.onPrimary} />
                <Text style={styles.primaryBtnText}>{t('common.save')}</Text>
              </>
            )}
          </Pressable>
        </View>
      </View>
    </View>
  );
}

// Matches styles.input below but as a plain CSS object — react-native-web's
// StyleSheet output isn't usable on a raw <input>.
const webDateInputStyle: React.CSSProperties = {
  fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.foreground,
  backgroundColor: colors.mutedBg, borderRadius: radius.sm, border: 'none',
  paddingLeft: spacing.sm, paddingRight: spacing.sm, paddingTop: 8, paddingBottom: 8,
  minHeight: 40, width: '100%', boxSizing: 'border-box',
};

const styles = StyleSheet.create({
  backdrop: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(10,15,30,0.45)',
    alignItems: 'center', justifyContent: 'center', zIndex: 50,
  },
  card: {
    width: 340, backgroundColor: colors.surface, borderRadius: radius.lg,
    padding: spacing.lg, gap: spacing.xs, ...shadow.md,
  },
  title: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 20, color: colors.foreground, marginBottom: spacing.xs },
  label: { fontFamily: 'Barlow_600SemiBold', fontSize: 12, color: colors.muted, marginTop: spacing.xs },
  input: {
    fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.foreground,
    backgroundColor: colors.mutedBg, borderRadius: radius.sm,
    paddingHorizontal: spacing.sm, paddingVertical: 8, minHeight: 40,
  },
  errorText: { fontFamily: 'Barlow_400Regular', fontSize: 11, color: colors.destructive },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  secondaryBtn: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    paddingVertical: spacing.sm, borderRadius: radius.md,
    borderWidth: 1.5, borderColor: colors.border, minHeight: 44,
  },
  secondaryBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 14, color: colors.primary },
  primaryBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.sm, minHeight: 44,
  },
  primaryBtnDisabled: { opacity: 0.4 },
  primaryBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 14, color: colors.onPrimary },
});
