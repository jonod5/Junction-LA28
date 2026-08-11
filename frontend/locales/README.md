# Locale files

`en.json` is the source of truth — every key originates here. `es.json`, `fr.json`, and `zh-Hans.json` are first-pass translations generated directly (no third-party translation API), matching every key and interpolation placeholder (`{{name}}`, `{{count}}`, etc.) in `en.json`.

## ⚠️ Native-speaker review required before public launch

The Spanish, French, and Simplified Chinese translations in this directory are a solid first pass, not a verified final version. They have **not** been reviewed by a native speaker. Before this app is publicly launched:

- Have a native speaker of each language review every string for accuracy, tone, and natural phrasing.
- Pay particular attention to transit/logistics terminology (e.g. "TDM", "PUDO", "GBFS") and LA28-specific phrasing, which may not have a single standard translation.
- Venue-specific content (parking, curb access, congestion notes) is translated separately — see `app/services/venue_translation.py` and the `venue_translation` table; those rows carry their own `reviewed` flag and need the same review pass.

## Adding a new key

Add it to `en.json` first, then the same key path to `es.json`, `fr.json`, and `zh-Hans.json`. Keep the interpolation variables identical across all four files — `lib/i18n.ts` doesn't validate this at build time, so a mismatched placeholder will silently render as literal text (`{{name}}`) instead of the value.

## Pluralization

Keys needing a count use i18next's `_one`/`_other` suffixes (e.g. `stop_one` / `stop_other`), selected automatically by `t('key', { count: n })`. Simplified Chinese has no singular/plural distinction, so `zh-Hans.json` only defines the `_other` form for those keys — i18next's plural rules for `zh` never select `_one`, so omitting it is intentional, not a gap.
