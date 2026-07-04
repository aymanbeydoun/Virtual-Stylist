import { LinearGradient } from "expo-linear-gradient";
import { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { useAura } from "@/state/aura";
import { useAccent, useBackgroundDesign } from "@/state/theme";

/**
 * ThemeEngine — Project Verve, Pillar 3 (ambient, dynamic UI).
 *
 * The app-wide canvas. Resolves the active colour-field in priority order:
 *
 *   1. live outfit aura (set when the stylist generates looks)
 *   2. the user's chosen backdrop design (You tab)
 *
 * Transitions are never a hard cut: the previous gradient stays mounted while
 * the next one fades in over it on the UI thread (Reanimated), giving the
 * whole app a slow, breathing "alive" feel whenever the mood shifts.
 */
type Stops = [string, string, ...string[]];

const FADE_MS = 900;

export function ThemeEngine() {
  const design = useBackgroundDesign();
  const accent = useAccent();
  const aura = useAura((s) => s.aura);

  const base: Stops = design.fromAccent
    ? [`${accent.color}40`, "#0A0B0E", "#060709"]
    : ([...design.colors] as Stops);
  const target: Stops = aura ? aura.gradient : base;
  const targetKey = target.join("|");

  const [layers, setLayers] = useState<{ under: Stops; over: Stops }>({
    under: target,
    over: target,
  });
  const progress = useSharedValue(1);

  useEffect(() => {
    setLayers((prev) => ({ under: prev.over, over: target }));
    progress.value = 0;
    progress.value = withTiming(1, {
      duration: FADE_MS,
      easing: Easing.out(Easing.cubic),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKey]);

  const overStyle = useAnimatedStyle(() => ({ opacity: progress.value }));

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <LinearGradient colors={layers.under} style={StyleSheet.absoluteFill} />
      <Animated.View style={[StyleSheet.absoluteFill, overStyle]}>
        <LinearGradient colors={layers.over} style={StyleSheet.absoluteFill} />
      </Animated.View>
    </View>
  );
}
