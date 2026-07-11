import React, { createContext, useCallback, useContext, useState } from 'react';
import { api, DirectionStep, Leg, Stop, Trip } from './api';

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
}

const TripContext = createContext<TripContextValue | null>(null);

export function TripProvider({ children }: { children: React.ReactNode }) {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [directionSteps, setDirectionSteps] = useState<Record<string, DirectionStep[]>>({});

  const clearError = useCallback(() => setError(null), []);

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

  return (
    <TripContext.Provider
      value={{ trip, loading, error, clearError, createTrip, addStop, removeStop, reorderStops, saveLeg, directionSteps, saveDirectionSteps }}
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
