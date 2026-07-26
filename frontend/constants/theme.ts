// ── Bluebell + twilight palette ────────────────────────────────────────────
// Primary is back to Bluebell (the original LA28 brand blue), accented with
// an adjacent violet/purple — a blue -> indigo -> purple progression, with
// warm gold and a green "eco" as the two functional counterpoints so the
// whole scheme doesn't read as one temperature.
export const brand = {
  bluebell: '#2B6CB0',   // primary — the original LA28 blue
  indigo: '#6366F1',     // adjacent purple, one step toward violet from bluebell
  violet: '#9333EA',     // adjacent purple, one step further — secondary
  gold: '#F59E0B',       // warm counterpoint — Olympic gold
  sagebrush: '#48BB78',  // green counterpoint — "eco" / sustainability
} as const;

export const colors = {
  primary: brand.bluebell,
  onPrimary: '#FFFFFF',
  secondary: brand.violet,        // purple pop — transit / map
  gold: brand.gold,               // badges, active nav, "best option"
  accent: brand.indigo,           // the adjacent-purple accent, between primary and secondary
  eco: brand.sagebrush,           // green counterpoint — banners / grounding accent

  // ── Backgrounds — cool blue-white ─────────────────────────────────────────
  background: '#F0F5FF',
  surface: '#FFFFFF',
  mutedBg: '#E4ECFF',

  // ── Text ──────────────────────────────────────────────────────────────────
  foreground: '#0A0F1E',
  muted: '#4A5580',
  mutedFg: '#8896B8',

  // ── Structure ─────────────────────────────────────────────────────────────
  border: '#C0CFF5',

  // ── State ─────────────────────────────────────────────────────────────────
  destructive: '#DC2626',
  success: '#059669',

  // ── Semantic ──────────────────────────────────────────────────────────────
  transitBadge: brand.violet,
  drivingWarning: '#DC2626',
} as const;

// Blue -> indigo -> violet sweep — the primary/accent/secondary progression
// as one continuous "twilight" ramp, gold as a warm cap at the end.
export const gradients = {
  twilight: [brand.bluebell, brand.indigo, brand.violet, brand.gold] as [
    string, string, string, string,
  ],
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

// Angular radii — athletic / kinetic brutalism feel
export const radius = {
  sm: 4,
  md: 8,
  lg: 14,
  full: 9999,
} as const;

// Blue-tinted shadows for depth with brand alignment
export const shadow = {
  sm: {
    shadowColor: brand.bluebell,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.10,
    shadowRadius: 8,
    elevation: 3,
  },
  md: {
    shadowColor: brand.bluebell,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.16,
    shadowRadius: 20,
    elevation: 6,
  },
} as const;
