// Stated-preference (SP) survey — its own flow, separate from the trip
// planner. Consent -> a sequence of choice tasks -> thank-you. Sessions are
// always anonymous unless a signed-in user explicitly opts in (see
// handleAgree's attachAccount — no UI for that opt-in yet, off by default).
//
// PLACEHOLDER CONSENT: the text below is a stand-in, not IRB-approved
// language. Swap CONSENT_TITLE/CONSENT_BODY for the real approved text
// before any live data collection — this phase (database + frontend +
// ingest skeleton) explicitly does not collect real respondent data.
import { Feather } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { OptionCard, type OptionCardMetric } from '@/components/OptionCard';
import { colors, radius, shadow, spacing } from '@/constants/theme';
import { api, type SPChoiceTask } from '@/lib/api';

const CONSENT_TITLE = 'Travel Survey';
const CONSENT_BODY =
  "This is a placeholder consent screen " +
  "In this survey you'll see a series of " +
  "hypothetical trip options and pick the one you'd choose. Responses are " +
  "anonymous; no personal information is collected. Real data collection ";

/** mode_label is free text from the CSV, not a fixed enum — pick a
 * reasonable icon by keyword rather than requiring an exact match. */
function iconForModeLabel(label: string): React.ComponentProps<typeof Feather>['name'] {
  const l = label.toLowerCase();
  if (l.includes('transit') || l.includes('metro') || l.includes('rail') || l.includes('bus')) return 'navigation';
  if (l.includes('bike') || l.includes('bicycle')) return 'activity';
  if (l.includes('scooter')) return 'zap';
  if (l.includes('walk')) return 'user';
  if (l.includes('rideshare') || l.includes('drive') || l.includes('car')) return 'truck';
  return 'map-pin';
}

type Phase = 'consent' | 'loading' | 'task' | 'thankyou' | 'error';

export default function SurveyScreen() {
  const params = useLocalSearchParams<{ surveyId?: string }>();
  // Defaults to 1 — the sample survey is the first one any fresh ingest
  // creates. Pass ?surveyId=N to point at a different one.
  const surveyId = params.surveyId ? Number(params.surveyId) : 1;

  const [phase, setPhase] = useState<Phase>('consent');
  const [respondentId, setRespondentId] = useState<string | null>(null);
  const [task, setTask] = useState<SPChoiceTask | null>(null);
  const [taskNumber, setTaskNumber] = useState(0);
  const [totalTasks, setTotalTasks] = useState(0);
  const [selectedAltId, setSelectedAltId] = useState<number | null>(null);
  const [shownAt, setShownAt] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadNextTask = useCallback(async (currentRespondentId: string) => {
    setPhase('loading');
    setError(null);
    try {
      const next = await api.getNextSurveyTask(currentRespondentId);
      setTotalTasks(next.total_tasks);
      if (next.completed || !next.task) {
        await api.completeSurveySession(currentRespondentId);
        setPhase('thankyou');
        return;
      }
      setTask(next.task);
      setTaskNumber(next.task_number);
      setSelectedAltId(null);
      setShownAt(new Date().toISOString());
      setPhase('task');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not load the next question.');
      setPhase('error');
    }
  }, []);

  const handleAgree = async () => {
    setPhase('loading');
    setError(null);
    try {
      // attachAccount stays false — anonymous by default, no opt-in UI yet.
      const session = await api.startSurveySession(surveyId, false);
      setRespondentId(session.respondent_id);
      await loadNextTask(session.respondent_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not start the survey.');
      setPhase('error');
    }
  };

  const handleNext = async () => {
    if (!respondentId || !task || selectedAltId == null || !shownAt) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.recordSurveyChoice(respondentId, task.id, selectedAltId, shownAt);
      await loadNextTask(respondentId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not record your choice.');
    } finally {
      setSubmitting(false);
    }
  };

  if (phase === 'consent') {
    return (
      <SafeAreaView style={styles.screen}>
        <ScrollView contentContainerStyle={styles.centeredContent}>
          <View style={styles.placeholderTag}>
            <Feather name="alert-triangle" size={12} color={colors.drivingWarning} />
            <Text style={styles.placeholderTagText}>PLACEHOLDER</Text>
          </View>
          <Text style={styles.title}>{CONSENT_TITLE}</Text>
          <Text style={styles.body}>{CONSENT_BODY}</Text>
          <Pressable style={styles.primaryBtn} onPress={handleAgree} accessibilityRole="button">
            <Text style={styles.primaryBtnText}>  I agree — continue  </Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    );
  }

  if (phase === 'loading') {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (phase === 'error') {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.centered}>
          <Feather name="alert-circle" size={28} color={colors.destructive} />
          <Text style={styles.errorText}>{error}</Text>
          <Pressable
            style={styles.secondaryBtn}
            onPress={() => (respondentId ? loadNextTask(respondentId) : handleAgree())}
            accessibilityRole="button"
          >
            <Text style={styles.secondaryBtnText}>Retry</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (phase === 'thankyou') {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.centered}>
          <Feather name="check-circle" size={32} color={colors.success} />
          <Text style={styles.title}>Thank you</Text>
          <Text style={styles.body}>Your responses have been recorded. You can close this window.</Text>
        </View>
      </SafeAreaView>
    );
  }

  // phase === 'task'
  if (!task) return null;
  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.taskContent}>
        <Text style={styles.progress}>Question {taskNumber} of {totalTasks}</Text>
        <Text style={styles.taskPrompt}>Which of these trips would you choose?</Text>

        {task.alternatives.map((alt) => {
          const metrics: OptionCardMetric[] = [
            alt.travel_time_min != null && { icon: 'clock', text: `${alt.travel_time_min} min` },
            alt.cost_usd != null && { icon: 'dollar-sign', text: alt.cost_usd.toFixed(2) },
            alt.walk_time_min != null && { icon: 'map', text: `${alt.walk_time_min} min walk` },
            alt.transfers != null && { icon: 'repeat', text: `${alt.transfers} transfer${alt.transfers === 1 ? '' : 's'}` },
          ].filter((m): m is OptionCardMetric => Boolean(m));

          const selected = selectedAltId === alt.id;
          return (
            <OptionCard
              key={alt.id}
              icon={iconForModeLabel(alt.mode_label)}
              label={alt.mode_label}
              variant={selected ? 'selected' : 'default'}
              metrics={metrics}
              onPress={() => setSelectedAltId(alt.id)}
              accessibilityLabel={`Choose ${alt.mode_label}`}
            >
              <View style={styles.radioRow}>
                <Feather
                  name={selected ? 'check-circle' : 'circle'}
                  size={16}
                  color={selected ? colors.primary : colors.mutedFg}
                />
                <Text style={[styles.radioLabel, selected && { color: colors.primary }]}>
                  {selected ? 'Selected' : 'Select this option'}
                </Text>
              </View>
            </OptionCard>
          );
        })}

        {error && <Text style={styles.errorTextInline}>{error}</Text>}

        <Pressable
          style={[styles.primaryBtn, (selectedAltId == null || submitting) && styles.primaryBtnDisabled]}
          onPress={handleNext}
          disabled={selectedAltId == null || submitting}
          accessibilityRole="button"
        >
          {submitting ? (
            <ActivityIndicator color={colors.onPrimary} size="small" />
          ) : (
            <Text style={styles.primaryBtnText}>Next</Text>
          )}
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.sm, padding: spacing.xl },
  centeredContent: { flexGrow: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.md, padding: spacing.xl, maxWidth: 480, alignSelf: 'center' },
  taskContent: { padding: spacing.md, gap: spacing.md, maxWidth: 560, width: '100%', alignSelf: 'center', paddingBottom: spacing.xxl },
  placeholderTag: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: colors.drivingWarning,
    borderRadius: radius.sm, paddingHorizontal: spacing.sm, paddingVertical: 4,
  },
  placeholderTagText: { fontFamily: 'Barlow_700Bold', fontSize: 11, color: colors.drivingWarning, letterSpacing: 0.4 },
  title: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 24, color: colors.foreground, textAlign: 'center' },
  body: { fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.muted, textAlign: 'center', lineHeight: 21 },
  progress: { fontFamily: 'Barlow_700Bold', fontSize: 12, color: colors.muted, letterSpacing: 0.6, textTransform: 'uppercase' },
  taskPrompt: { fontFamily: 'BarlowCondensed_700Bold', fontSize: 20, color: colors.foreground, marginBottom: -spacing.xs },
  radioRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  radioLabel: { fontFamily: 'Barlow_500Medium', fontSize: 12, color: colors.mutedFg },
  errorText: { fontFamily: 'Barlow_400Regular', fontSize: 14, color: colors.destructive, textAlign: 'center' },
  errorTextInline: { fontFamily: 'Barlow_400Regular', fontSize: 12, color: colors.destructive },
  primaryBtn: {
    backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.sm,
    alignItems: 'center', justifyContent: 'center', minHeight: 44, ...shadow.sm,
  },
  primaryBtnDisabled: { opacity: 0.4 },
  primaryBtnText: { fontFamily: 'Barlow_700Bold', fontSize: 15, color: colors.onPrimary },
  secondaryBtn: {
    borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.md,
    paddingVertical: spacing.sm, paddingHorizontal: spacing.lg, minHeight: 40, alignItems: 'center', justifyContent: 'center',
  },
  secondaryBtnText: { fontFamily: 'Barlow_600SemiBold', fontSize: 13, color: colors.primary },
});
