import { DarkTheme, NavigationContainer } from "@react-navigation/native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AppBackground } from "@/components/AppBackground";
import { RootNavigator } from "@/navigation/RootNavigator";
import { useGamification } from "@/state/gamification";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

// Transparent so the themed AppBackground shows through every screen.
const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: "transparent" },
};

export default function App() {
  // Count today's visit once per app open to advance the status level. Wait for
  // the persisted streak to hydrate first so we don't clobber the stored count.
  useEffect(() => {
    const register = () => useGamification.getState().registerVisit();
    if (useGamification.persist.hasHydrated()) register();
    return useGamification.persist.onFinishHydration(register);
  }, []);

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <View style={{ flex: 1 }}>
          <AppBackground />
          <NavigationContainer theme={navTheme}>
            <RootNavigator />
            <StatusBar style="light" />
          </NavigationContainer>
        </View>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
