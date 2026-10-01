import { Tabs } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import JunctionLogo from '@/components/JunctionLogo';
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
        headerTitleStyle: styles.title,
        headerShown: useClientOnlyValue(false, true),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'JUNCTION',
          headerTitle: ({ children, tintColor }) => (
            <View style={styles.brand}>
              <JunctionLogo size={28} roadColor="#FFFFFF" />
              <Text style={[styles.title, { color: tintColor }]}>{children}</Text>
            </View>
          ),
        }}
      />
      {/* Native-only fallback screens (web replaces both with index.web.tsx). */}
      <Tabs.Screen name="map" options={{ href: null }} />
      <Tabs.Screen name="routes" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  title: {
    fontFamily: 'BarlowCondensed_700Bold',
    fontSize: 22,
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
});
