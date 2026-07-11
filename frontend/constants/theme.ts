export const colors = {
  primary: '#EA580C',
  onPrimary: '#FFFFFF',
  secondary: '#0891B2',
  accent: '#D97706',
  background: '#FFF7ED',
  surface: '#FFFFFF',
  foreground: '#0F172A',
  muted: '#78716C',
  mutedBg: '#FDF4F0',
  border: '#FCEAE1',
  destructive: '#DC2626',
  success: '#16A34A',
  policyBanner: '#4C1D95',
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

export const radius = {
  sm: 8,
  md: 16,
  lg: 24,
  full: 9999,
} as const;

export const shadow = {
  sm: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 12,
    elevation: 4,
  },
} as const;
