// ── LA28 brand palette ────────────────────────────────────────────────────
// Poppy, Scarlet Flax, Bluebell, Sagebrush — the official LA28 2028 hues.
// Kept as named exports too so gradient stops can reference them directly
// instead of duplicating hex values.
export const brand = {
  poppy: '#FF6600',
  scarletFlax: '#E60067',
  bluebell: '#2B6CB0',
  sagebrush: '#48BB78',
} as const;

export const colors = {
  // ── Bluebell — deep electric sky blue ─────────────────────────────────────
  primary: brand.bluebell,
  onPrimary: '#FFFFFF',
  secondary: brand.scarletFlax,  // saturated magenta-pink — transit / map
  gold: '#F59E0B',                // Olympic gold — badges, active nav, sunset highlight
  accent: brand.poppy,            // radiant orange — CTAs, warm contrast

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
  success: '#059669',             // distinct from primary's sagebrush so "done" still reads apart from "brand"

  // ── Semantic ──────────────────────────────────────────────────────────────
  transitBadge: brand.scarletFlax,
  drivingWarning: '#DC2626',
} as const;

// Reusable "LA28 sunset" gradient stops — magenta into orange into gold,
// mirroring the brand's radiating sunset motif. Used with expo-linear-gradient
// for the header and hero surfaces; kept as plain hex arrays so both
// LinearGradient (native+web) and raw CSS strings (web-only surfaces) can
// consume the same source of truth.
export const gradients = {
  sunset: [brand.scarletFlax, brand.poppy, '#F59E0B'] as [string, string, string],
  sunsetSoft: ['#FDE9F0', '#FFE3CC', '#FFF3D6'] as [string, string, string],
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
