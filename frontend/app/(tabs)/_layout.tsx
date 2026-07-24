import { Feather } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

import { useClientOnlyValue } from '@/components/useClientOnlyValue';
import { gradients } from '@/constants/theme';

const NAV_BG = '#070C1C';       // deep navy
const NAV_ACTIVE = '#F59E0B';   // Olympic gold
const NAV_INACTIVE = '#5B7CB8'; // muted blue-gray

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: NAV_ACTIVE,
        tabBarInactiveTintColor: NAV_INACTIVE,
        tabBarStyle: {
          backgroundColor: NAV_BG,
          borderTopColor: '#1A2E5C',
          borderTopWidth: 1,
        },
        tabBarLabelStyle: {
          fontFamily: 'Barlow_600SemiBold',
          fontSize: 11,
          letterSpacing: 0.5,
        },
        // Signature "LA28 sunset" gradient header — magenta into orange into
        // gold — instead of a flat brand color.
        headerBackground: () => (
          <LinearGradient
            colors={gradients.sunset}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={{ flex: 1 }}
          />
        ),
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
      <Tabs.Screen
        name="index"
        options={{
          title: 'Planner',
          tabBarLabel: 'Planner',
          tabBarIcon: ({ color, size }) => (
            <Feather name="map" size={size} color={color} />
          ),
        }}
      />
      {/* Native-only fallback screens (web replaces both with index.web.tsx). */}
      <Tabs.Screen name="map" options={{ href: null }} />
      <Tabs.Screen name="routes" options={{ href: null }} />
    </Tabs>
  );
}
