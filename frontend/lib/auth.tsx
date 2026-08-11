// Auth session state — separate from lib/store.tsx's TripContext on purpose.
// Trip-building logic and sign-in state are independent concerns: the
// planner must keep working with this provider absent a session entirely.
import type { Session, User } from '@supabase/supabase-js';
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { api, type Account } from './api';
import i18next, { changeLanguage, SUPPORTED_LANGUAGES, type SupportedLanguage } from './i18n';
import { isSupabaseConfigured, supabase } from './supabase';

function isSupportedLanguage(value: unknown): value is SupportedLanguage {
  return typeof value === 'string' && (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

interface AuthContextValue {
  session: Session | null;
  user: User | null;
  /** True until the initial session read (from storage) resolves. */
  loading: boolean;
  /** False when EXPO_PUBLIC_SUPABASE_URL/ANON_KEY aren't set — callers should hide sign-in UI. */
  isConfigured: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  /** Our backend's mutable profile mirror (display_name, avatar_url,
   *  preferences) — null until fetched. Supabase's own user_metadata (the
   *  Google name/photo) is read-only from this app's side, so anything the
   *  user can actually edit — display name, default travel modes — lives
   *  here instead. Shared across the app (AccountMenu, Settings, the
   *  planner's onboarding pre-fill) so a change in one place is visible in
   *  the others without each fetching its own copy. */
  account: Account | null;
  refreshAccount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(isSupabaseConfigured);
  const [account, setAccount] = useState<Account | null>(null);

  const refreshAccount = useCallback(async () => {
    if (!isSupabaseConfigured) return;
    try {
      setAccount(await api.getAccount());
    } catch {
      // Not signed in yet, or the request failed — leave the previous
      // value in place rather than flashing a null/loading state.
    }
  }, []);

  const userId = session?.user?.id;
  useEffect(() => {
    if (userId) {
      refreshAccount();
    } else {
      setAccount(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // A signed-in user's saved language preference wins once it's loaded —
  // i18next already started from the local cache/device language at import
  // time (see lib/i18n.ts), this just corrects it a moment later if the
  // account says otherwise. Also re-syncs the local cache, so the next
  // anonymous-until-loaded boot on this device starts in the right language
  // immediately.
  useEffect(() => {
    const lang = account?.preferences?.language;
    if (isSupportedLanguage(lang) && lang !== i18next.language) {
      changeLanguage(lang);
    }
  }, [account]);

  useEffect(() => {
    if (!isSupabaseConfigured) return;
    let cancelled = false;
    supabase.auth.getSession().then(({ data }) => {
      if (!cancelled) {
        setSession(data.session);
        setLoading(false);
      }
    });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => {
      cancelled = true;
      subscription.subscription.unsubscribe();
    };
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!isSupabaseConfigured) return;
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: typeof window !== 'undefined' ? window.location.origin : undefined,
      },
    });
  }, []);

  const signOut = useCallback(async () => {
    if (!isSupabaseConfigured) return;
    await supabase.auth.signOut();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        loading,
        isConfigured: isSupabaseConfigured,
        signInWithGoogle,
        signOut,
        account,
        refreshAccount,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
