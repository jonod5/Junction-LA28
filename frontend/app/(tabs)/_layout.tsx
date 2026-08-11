import { Tabs } from 'expo-router';

import { useClientOnlyValue } from '@/components/useClientOnlyValue';
import { colors } from '@/constants/theme';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        // Single-screen app now (index.web.tsx unifies Builder/Map/Routes) —
        // no bottom tab bar to switch between, so hide the strip entirely.
        tabBarStyle: { display: 'none' },
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: '#FFFFFF',
        headerTitleStyle: {
          fontFamily: 'BarlowCondensed_700Bold',
          fontSize: 22,
          letterSpacing: 2,
          textTransform: 'uppercase',
        },
        headerShown: useClientOnlyValue(false, true),
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'JUNCTION' }} />
      {/* Native-only fallback screens (web replaces both with index.web.tsx). */}
      <Tabs.Screen name="map" options={{ href: null }} />
      <Tabs.Screen name="routes" options={{ href: null }} />
    </Tabs>
  );
}
