import { ArchivoBlack_400Regular } from "@expo-google-fonts/archivo-black";
import {
  SpaceGrotesk_400Regular,
  SpaceGrotesk_500Medium,
  SpaceGrotesk_700Bold,
} from "@expo-google-fonts/space-grotesk";
import { DarkTheme, NavigationContainer } from "@react-navigation/native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ThemeEngine } from "@/components/ThemeEngine";
import { RootNavigator } from "@/navigation/RootNavigator";
import { useGamification } from "@/state/gamification";
import { palette } from "@/theme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

// Transparent so the ThemeEngine canvas shows through every screen.
const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: "transparent" },
};

export default function App() {
  const [fontsLoaded, fontError] = useFonts({
    ArchivoBlack_400Regular,
    SpaceGrotesk_400Regular,
    SpaceGrotesk_500Medium,
    SpaceGrotesk_700Bold,
  });

  // Count today's visit once per app open to advance the status level. Wait for
  // the persisted streak to hydrate first so we don't clobber the stored count.
  useEffect(() => {
    const register = () => useGamification.getState().registerVisit();
    if (useGamification.persist.hasHydrated()) register();
    return useGamification.persist.onFinishHydration(register);
  }, []);

  // Hold on the ink canvas until the display/body fonts are ready.
  if (!fontsLoaded && !fontError) {
    return <View style={{ flex: 1, backgroundColor: palette.background }} />;
  }

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <View style={{ flex: 1 }}>
          <ThemeEngine />
          <NavigationContainer theme={navTheme}>
            <RootNavigator />
            <StatusBar style="light" />
          </NavigationContainer>
        </View>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
