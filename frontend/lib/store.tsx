import React, { createContext, useCallback, useContext, useState } from 'react';
import {
  api,
  DirectionStep,
  Leg,
  RouteMode,
  RouteOptimizeResult,
  SavedLegSnapshot,
  SavedPlanSnapshot,
  Stop,
  Trip,
} from './api';
// Module-level i18next instance, not the useTranslation hook — this is a
// plain callback (not a component), and only needs the current language at
// call time, not reactive re-rendering.
import i18next from './i18n';

/** All non-car modes the route engine can rank (mirrors route_engine.MODE_LABEL). */
export const ROUTE_MODES: RouteMode[] = ['transit', 'metro_micro', 'bike', 'scooter', 'walk', 'ridehail'];

function legKey(fromId: number, toId: number): string {
  return `${fromId}-${toId}`;
}

interface TripContextValue {
  trip: Trip | null;
  loading: boolean;
  error: string | null;
  clearError: () => void;
  createTrip: (name: string) => Promise<Trip | null>;
  addStop: (venueId: number | null, name: string, lat: number, lng: number) => Promise<Stop | null>;
  removeStop: (stopId: number) => Promise<void>;
  reorderStops: (order: { stop_id: number; order_index: number }[]) => Promise<void>;
  saveLeg: (leg: Leg) => void;
  /** Per-leg step data keyed by "fromStopId-toStopId" — used by map for segment rendering */
  directionSteps: Record<string, DirectionStep[]>;
  saveDirectionSteps: (fromId: number, toId: number, steps: DirectionStep[]) => void;

  // ── Mode preferences (session-only; feeds /api/routes/optimize) ────────────
  /** null = not chosen yet (onboarding not completed); array = explicit allow-list. */
  preferences: RouteMode[] | null;
  setPreferences: (modes: RouteMode[]) => void;

  // ── Route optimization engine results, per consecutive stop pair ───────────
  routeOptions: Record<string, RouteOptimizeResult | null>;
  routeOptionsLoading: Record<string, boolean>;
  routeOptionsError: Record<string, string | null>;
  selectedOptionId: Record<string, string | null>;
  optimizeLeg: (
    from: Stop,
    to: Stop,
    opts?: { preferredOptionId?: string; preferencesOverride?: RouteMode[] | null },
  ) => Promise<void>;
  selectRouteOption: (fromId: number, toId: number, optionId: string) => void;

  // ── Saved itineraries ────────────────────────────────────────────────────
  /** True while a saved itinerary is being rehydrated into a fresh trip. */
  hydrating: boolean;
  /** Builds the saved_plan snapshot (stops + selected option per leg) from
   *  the current session — the exact shape /api/itineraries stores. */
  buildSnapshot: () => SavedPlanSnapshot;
  /** Replaces the current trip with a brand-new one built from a saved
   *  snapshot, then re-runs live route optimization for every leg (this is
   *  a deliberate live refresh, not just replaying the snapshot's numbers —
   *  see the Phase 3 auto-refresh decision) and restores each leg's
   *  previous mode-combo selection when the fresh results still offer it. */
  hydrateFromSnapshot: (snapshot: SavedPlanSnapshot) => Promise<boolean>;
}

const TripContext = createContext<TripContextValue | null>(null);

export function TripProvider({ children }: { children: React.ReactNode }) {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [directionSteps, setDirectionSteps] = useState<Record<string, DirectionStep[]>>({});

  const [preferences, setPreferencesState] = useState<RouteMode[] | null>(null);
  const [routeOptions, setRouteOptions] = useState<Record<string, RouteOptimizeResult | null>>({});
  const [routeOptionsLoading, setRouteOptionsLoading] = useState<Record<string, boolean>>({});
  const [routeOptionsError, setRouteOptionsError] = useState<Record<string, string | null>>({});
  const [selectedOptionId, setSelectedOptionId] = useState<Record<string, string | null>>({});

  const [hydrating, setHydrating] = useState(false);

  const clearError = useCallback(() => setError(null), []);

  const setPreferences = useCallback((modes: RouteMode[]) => {
    setPreferencesState(modes);
  }, []);

  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const createTrip = useCallback(
    async (name: string): Promise<Trip | null> => {
      const t = await run(() => api.createTrip(name));
      if (t) setTrip(t);
      return t;
    },
    [run],
  );

  const addStop = useCallback(
    async (venueId: number | null, name: string, lat: number, lng: number): Promise<Stop | null> => {
      if (!trip) return null;
      const body = venueId !== null
        ? { venue_id: venueId, name, lat, lng }
        : { name, lat, lng };
      const stop = await run(() => api.addStop(trip.id, body));
      if (stop) {
        setTrip((prev) => prev && { ...prev, stops: [...prev.stops, stop] });
      }
      return stop;
    },
    [trip, run],
  );

  const removeStop = useCallback(
    async (stopId: number): Promise<void> => {
      if (!trip) return;
      await run(() => api.removeStop(trip.id, stopId));
      setTrip((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          stops: prev.stops.filter((s) => s.id !== stopId),
          legs: prev.legs.filter(
            (l) => l.from_stop_id !== stopId && l.to_stop_id !== stopId,
          ),
        };
      });
    },
    [trip, run],
  );

  const reorderStops = useCallback(
    async (order: { stop_id: number; order_index: number }[]): Promise<void> => {
      if (!trip) return;
      // Optimistic update
      const newStops = [...trip.stops]
        .map((s) => {
          const o = order.find((x) => x.stop_id === s.id);
          return o ? { ...s, order_index: o.order_index } : s;
        })
        .sort((a, b) => a.order_index - b.order_index);
      setTrip((prev) => prev && { ...prev, stops: newStops });
      await run(() => api.reorderStops(trip.id, order));
    },
    [trip, run],
  );

  const saveLeg = useCallback((leg: Leg) => {
    setTrip((prev) => {
      if (!prev) return prev;
      const filtered = prev.legs.filter(
        (l) =>
          !(
            l.from_stop_id === leg.from_stop_id &&
            l.to_stop_id === leg.to_stop_id &&
            l.mode === leg.mode
          ),
      );
      return { ...prev, legs: [...filtered, leg] };
    });
  }, []);

  const saveDirectionSteps = useCallback((fromId: number, toId: number, steps: DirectionStep[]) => {
    setDirectionSteps((prev) => ({ ...prev, [`${fromId}-${toId}`]: steps }));
  }, []);

  const optimizeLeg = useCallback(
    async (
      from: Stop,
      to: Stop,
      opts?: { preferredOptionId?: string; preferencesOverride?: RouteMode[] | null },
    ): Promise<void> => {
      const key = legKey(from.id, to.id);
      // preferencesOverride lets a caller bypass the (possibly stale, within
      // the same tick) `preferences` closure — used when rehydrating a saved
      // itinerary, where the preferences to use are known synchronously from
      // the snapshot rather than from context state that hasn't re-rendered yet.
      const prefsToUse = opts && 'preferencesOverride' in opts ? opts.preferencesOverride : preferences;
      setRouteOptionsLoading((prev) => ({ ...prev, [key]: true }));
      setRouteOptionsError((prev) => ({ ...prev, [key]: null }));
      try {
        const result = await api.optimizeRoutes({
          origin: { lat: from.lat, lng: from.lng },
          destination: { lat: to.lat, lng: to.lng },
          preferences: prefsToUse ?? null,
          language: i18next.language,
        });
        setRouteOptions((prev) => ({ ...prev, [key]: result }));
        // Restore a previously-selected mode combo when it's still offered
        // (e.g. rehydrating a saved itinerary); otherwise default to the
        // top-ranked (best-scoring) option.
        const preferredId = opts?.preferredOptionId;
        const restored = preferredId && result.options.some((o) => o.id === preferredId)
          ? preferredId
          : result.options[0]?.id ?? null;
        setSelectedOptionId((prev) => ({ ...prev, [key]: restored }));
      } catch (e: unknown) {
        setRouteOptionsError((prev) => ({
          ...prev,
          [key]: e instanceof Error ? e.message : 'Could not compute route options',
        }));
      } finally {
        setRouteOptionsLoading((prev) => ({ ...prev, [key]: false }));
      }
    },
    [preferences],
  );

  const selectRouteOption = useCallback((fromId: number, toId: number, optionId: string) => {
    setSelectedOptionId((prev) => ({ ...prev, [legKey(fromId, toId)]: optionId }));
  }, []);

  const buildSnapshot = useCallback((): SavedPlanSnapshot => {
    const orderedStops = [...(trip?.stops ?? [])].sort((a, b) => a.order_index - b.order_index);
    const legs: Record<string, SavedLegSnapshot> = {};
    orderedStops.slice(0, -1).forEach((from, i) => {
      const to = orderedStops[i + 1];
      const key = legKey(from.id, to.id);
      const res = routeOptions[key];
      const selId = selectedOptionId[key];
      const opt = res?.options.find((o) => o.id === selId);
      if (opt) legs[`${i}-${i + 1}`] = { selected_option: opt };
    });
    return {
      stops: orderedStops.map((s) => ({ venue_id: s.venue_id, name: s.name, lat: s.lat, lng: s.lng })),
      preferences,
      legs,
    };
  }, [trip, routeOptions, selectedOptionId, preferences]);

  const hydrateFromSnapshot = useCallback(
    async (snapshot: SavedPlanSnapshot): Promise<boolean> => {
      setHydrating(true);
      setError(null);
      try {
        const newTrip = await api.createTrip('My LA28 Trip');
        setTrip(newTrip);
        setRouteOptions({});
        setSelectedOptionId({});
        setRouteOptionsError({});
        setRouteOptionsLoading({});
        setPreferencesState(snapshot.preferences);

        const createdStops: Stop[] = [];
        for (const s of snapshot.stops) {
          const stop = await api.addStop(newTrip.id, {
            venue_id: s.venue_id ?? undefined,
            name: s.name,
            lat: s.lat,
            lng: s.lng,
          });
          createdStops.push(stop);
        }
        setTrip((prev) => (prev ? { ...prev, stops: createdStops } : prev));

        // Re-optimize every consecutive pair with live data — a deliberate
        // choice (not just replaying the snapshot's numbers) so a reopened
        // itinerary always reflects current prices and transit schedules.
        // Each leg's previous mode-combo selection is restored when the
        // fresh results still offer it, else falls back to the new top pick.
        for (let i = 0; i < createdStops.length - 1; i++) {
          const from = createdStops[i];
          const to = createdStops[i + 1];
          const preferredOptionId = snapshot.legs[`${i}-${i + 1}`]?.selected_option?.id;
          await optimizeLeg(from, to, { preferredOptionId, preferencesOverride: snapshot.preferences });
        }
        return true;
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Could not open this itinerary');
        return false;
      } finally {
        setHydrating(false);
      }
    },
    [optimizeLeg],
  );

  return (
    <TripContext.Provider
      value={{
        trip, loading, error, clearError, createTrip, addStop, removeStop, reorderStops, saveLeg,
        directionSteps, saveDirectionSteps,
        preferences, setPreferences,
        routeOptions, routeOptionsLoading, routeOptionsError, selectedOptionId,
        optimizeLeg, selectRouteOption,
        hydrating, buildSnapshot, hydrateFromSnapshot,
      }}
    >
      {children}
    </TripContext.Provider>
  );
}

export function useTrip(): TripContextValue {
  const ctx = useContext(TripContext);
  if (!ctx) throw new Error('useTrip must be used inside <TripProvider>');
  return ctx;
}
