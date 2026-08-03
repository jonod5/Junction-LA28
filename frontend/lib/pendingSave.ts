// Bridges the Save flow across a Supabase OAuth redirect. signInWithOAuth on
// web does a full-page redirect, which wipes all in-memory React state — so
// a signed-out "Save" tap stashes the in-progress plan here first, and the
// planner checks for it once the user comes back signed in.
import type { SavedPlanSnapshot } from './api';

const KEY = 'la28_pending_save';

export interface PendingSave {
  name: string;
  tripDate: string | null;
  tags: string[];
  snapshot: SavedPlanSnapshot;
}

export function stashPendingSave(pending: PendingSave): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(KEY, JSON.stringify(pending));
}

export function readPendingSave(): PendingSave | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PendingSave;
  } catch {
    return null;
  }
}

export function clearPendingSave(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(KEY);
}
