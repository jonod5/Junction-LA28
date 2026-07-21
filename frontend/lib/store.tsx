import React, { createContext, useCallback, useContext, useState } from 'react';
import { api, DirectionStep, Leg, RouteMode, RouteOptimizeResult, Stop, Trip } from './api';

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
  optimizeLeg: (from: Stop, to: Stop) => Promise<void>;
  selectRouteOption: (fromId: number, toId: number, optionId: string) => void;
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
    async (from: Stop, to: Stop): Promise<void> => {
      const key = legKey(from.id, to.id);
      setRouteOptionsLoading((prev) => ({ ...prev, [key]: true }));
      setRouteOptionsError((prev) => ({ ...prev, [key]: null }));
      try {
        const result = await api.optimizeRoutes({
          origin: { lat: from.lat, lng: from.lng },
          destination: { lat: to.lat, lng: to.lng },
          preferences,
        });
        setRouteOptions((prev) => ({ ...prev, [key]: result }));
        // Default to the top-ranked (best-scoring) option.
        setSelectedOptionId((prev) => ({ ...prev, [key]: result.options[0]?.id ?? null }));
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

  return (
    <TripContext.Provider
      value={{
        trip, loading, error, clearError, createTrip, addStop, removeStop, reorderStops, saveLeg,
        directionSteps, saveDirectionSteps,
        preferences, setPreferences,
        routeOptions, routeOptionsLoading, routeOptionsError, selectedOptionId,
        optimizeLeg, selectRouteOption,
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
