export const colors = {
  // ── Olympic electric blue ──────────────────────────────────────────────────
  primary: '#1B4FD8',
  onPrimary: '#FFFFFF',
  secondary: '#0891B2',    // cyan — transit / map
  gold: '#F59E0B',         // Olympic gold — badges, active nav
  accent: '#EA580C',       // warm orange — kept for contrast

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
  policyBanner: '#1E1B4B',
  transitBadge: '#0891B2',
  drivingWarning: '#DC2626',
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
    shadowColor: '#1B4FD8',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.10,
    shadowRadius: 8,
    elevation: 3,
  },
  md: {
    shadowColor: '#1B4FD8',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.16,
    shadowRadius: 20,
    elevation: 6,
  },
} as const;
