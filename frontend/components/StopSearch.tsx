import { Feather } from '@expo/vector-icons';
import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { AIRPORTS, AirportStub } from '@/constants/airports';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { VENUES, VenueStub } from '@/constants/venues';

export type SearchItem = VenueStub | AirportStub;

interface Props {
  /** Names already on the trip — excluded from results so they can't be re-added. */
  addedNames: string[];
  onSelect: (item: SearchItem) => void;
  placeholder?: string;
}

/** Type-ahead search across the 6 venues + 5 airports (FR-U2). */
export function StopSearch({ addedNames, onSelect, placeholder = 'Search venues or airports…' }: Props) {
  const [query, setQuery] = useState('');

  const results = useMemo<SearchItem[]>(() => {
    const q = query.trim().toLowerCase();
    const all: SearchItem[] = [...VENUES, ...AIRPORTS];
    const notAdded = all.filter((item) => !addedNames.includes(item.name));
    if (!q) return notAdded;
    return notAdded.filter((item) => {
      const haystack = item.kind === 'airport' ? `${item.name} ${item.code}` : item.name;
      return haystack.toLowerCase().includes(q);
    });
  }, [query, addedNames]);

  return (
    <View style={styles.wrap}>
      <View style={styles.inputRow}>
        <Feather name="search" size={15} color={colors.mutedFg} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder={placeholder}
          placeholderTextColor={colors.mutedFg}
          style={styles.input}
          accessibilityLabel="Search venues or airports"
          returnKeyType="search"
        />
        {query.length > 0 && (
          <Pressable onPress={() => setQuery('')} hitSlop={8} accessibilityLabel="Clear search">
            <Feather name="x" size={15} color={colors.mutedFg} />
          </Pressable>
        )}
      </View>

      <ScrollView style={styles.list} nestedScrollEnabled showsVerticalScrollIndicator={false}>
        {results.length === 0 && (
          <Text style={styles.empty}>No matches — try a different name.</Text>
        )}
        {results.map((item) => {
          const isVenue = item.kind === 'venue';
          return (
            <Pressable
              key={isVenue ? `v${item.id}` : `a${item.code}`}
              onPress={() => onSelect(item)}
              accessibilityRole="button"
              accessibilityLabel={`Add ${item.name}`}
              style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            >
              <View style={[styles.badge, { backgroundColor: isVenue ? colors.primary : colors.secondary }]}>
                <Feather name={isVenue ? 'map-pin' : 'navigation'} size={11} color="#fff" />
              </View>
              <View style={styles.rowText}>
                <Text style={styles.name} numberOfLines={1}>{item.name}</Text>
                <Text style={styles.sub} numberOfLines={1}>
                  {isVenue ? item.sport_use : `${item.code} · ${item.terminal_info}`}
                </Text>
              </View>
              <Feather name="plus-circle" size={16} color={colors.mutedFg} />
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.xs },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.mutedBg,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    minHeight: 40,
  },
  input: {
    flex: 1,
    fontFamily: 'Barlow_400Regular',
    fontSize: 14,
    color: colors.foreground,
    paddingVertical: 8,
  },
  list: { maxHeight: 220 },
  empty: {
    fontFamily: 'Barlow_400Regular',
    fontSize: 13,
    color: colors.mutedFg,
    padding: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: 6,
    ...shadow.sm,
  },
  rowPressed: { opacity: 0.7 },
  badge: {
    width: 22, height: 22, borderRadius: 11,
    alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  rowText: { flex: 1, minWidth: 0 },
  name: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.foreground },
  sub: { fontFamily: 'Barlow_400Regular', fontSize: 11, color: colors.muted, marginTop: 1 },
});
