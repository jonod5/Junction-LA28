// i18next setup — device-language detection on first load (expo-localization),
// manual override persisted afterward. Spanish/French/Simplified Chinese
// translations are a first pass (see locales/README.md) — not yet reviewed
// by a native speaker.
import * as Localization from 'expo-localization';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from '@/locales/en.json';
import es from '@/locales/es.json';
import fr from '@/locales/fr.json';
import zhHans from '@/locales/zh-Hans.json';

export const SUPPORTED_LANGUAGES = ['en', 'es', 'fr', 'zh-Hans'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
  'zh-Hans': '简体中文',
};

const STORAGE_KEY = 'la28_language';

function isSupported(value: string): value is SupportedLanguage {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

function detectDeviceLanguage(): SupportedLanguage {
  const locales = Localization.getLocales();
  for (const locale of locales) {
    const code = locale.languageCode;
    if (code === 'zh') return 'zh-Hans'; // the only Chinese variant we support
    if (code && isSupported(code)) return code;
  }
  return 'en';
}

function readStoredLanguage(): SupportedLanguage | null {
  if (typeof window === 'undefined') return null;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && isSupported(stored) ? stored : null;
}

/** Local cache used for anonymous users, and as an immediate-paint cache for
 *  signed-in users before their account preference has loaded. */
export function persistLanguageLocally(language: SupportedLanguage): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, language);
}

// Synchronous at import time — i18next needs a language before first render,
// and localStorage/device detection are both available immediately. A
// signed-in user's account.preferences.language (async) can still override
// this a moment later — see the sync effect in lib/auth.tsx.
const initialLanguage = readStoredLanguage() ?? detectDeviceLanguage();

i18next
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      es: { translation: es },
      fr: { translation: fr },
      'zh-Hans': { translation: zhHans },
    },
    lng: initialLanguage,
    fallbackLng: 'en',
    interpolation: { escapeValue: false }, // React already escapes
    returnEmptyString: false,
  });

export function changeLanguage(language: SupportedLanguage): void {
  i18next.changeLanguage(language);
  persistLanguageLocally(language);
}

export default i18next;
