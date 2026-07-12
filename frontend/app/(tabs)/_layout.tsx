import { Feather } from '@expo/vector-icons';
import { Tabs } from 'expo-router';

import { useClientOnlyValue } from '@/components/useClientOnlyValue';

const NAV_BG = '#070C1C';       // deep navy
const NAV_ACTIVE = '#F59E0B';   // Olympic gold
const NAV_INACTIVE = '#5B7CB8'; // muted blue-gray
const HEADER_BG = '#1B4FD8';    // electric blue

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
        headerStyle: { backgroundColor: HEADER_BG },
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
          title: 'My Trip',
          tabBarLabel: 'Builder',
          tabBarIcon: ({ color, size }) => (
            <Feather name="list" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="map"
        options={{
          title: 'Map',
          tabBarLabel: 'Map',
          tabBarIcon: ({ color, size }) => (
            <Feather name="map" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="routes"
        options={{
          title: 'Routes',
          tabBarLabel: 'Routes',
          tabBarIcon: ({ color, size }) => (
            <Feather name="navigation" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
