import { LinearGradient } from "expo-linear-gradient";
import { useEffect, useState } from "react";
import { StyleSheet, useWindowDimensions, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import Svg, { Circle, Defs, RadialGradient, Stop } from "react-native-svg";

import { useAura } from "@/state/aura";
import { useAccent, useBackgroundDesign } from "@/state/theme";

/**
 * ThemeEngine — the generative ambient canvas.
 *
 * Layer 1: the colour-field. Resolves in priority order — live outfit aura
 * (set the moment a vibe chip is tapped), then the user's chosen backdrop.
 * Transitions are never a hard cut: the previous gradient stays mounted while
 * the next fades in over it on the UI thread.
 *
 * Layer 2: the light leak. A slowly-breathing radial glow tinted by the
 * active aura (energetic vibes burn hotter; chill vibes stay as low-contrast
 * fog), so the ink canvas always feels faintly alive.
 */
type Stops = [string, string, ...string[]];

const FADE_MS = 900;

/** Peak opacity of the ambient glow per aura — hyper-focused for party moods. */
const GLOW_STRENGTH: Record<string, number> = {
  energetic: 0.34,
  hero: 0.34,
  bold: 0.3,
  playful: 0.24,
  romantic: 0.22,
  classy: 0.16,
  chill: 0.12,
  cozy: 0.12,
};

export function ThemeEngine() {
  const design = useBackgroundDesign();
  const accent = useAccent();
  const aura = useAura((s) => s.aura);
  const { width } = useWindowDimensions();

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
  const breath = useSharedValue(0);

  useEffect(() => {
    setLayers((prev) => ({ under: prev.over, over: target }));
    progress.value = 0;
    progress.value = withTiming(1, {
      duration: FADE_MS,
      easing: Easing.out(Easing.cubic),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKey]);

  useEffect(() => {
    breath.value = withRepeat(
      withTiming(1, { duration: 4200, easing: Easing.inOut(Easing.sin) }),
      -1,
      true,
    );
  }, [breath]);

  const overStyle = useAnimatedStyle(() => ({ opacity: progress.value }));

  const glowPeak = aura ? (GLOW_STRENGTH[aura.id] ?? 0.16) : 0.1;
  const glowStyle = useAnimatedStyle(() => ({
    opacity: glowPeak * (0.45 + breath.value * 0.55),
  }));
  const glowColor = aura ? aura.leak : accent.color;
  const glowSize = width * 1.3;

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <LinearGradient colors={layers.under} style={StyleSheet.absoluteFill} />
      <Animated.View style={[StyleSheet.absoluteFill, overStyle]}>
        <LinearGradient colors={layers.over} style={StyleSheet.absoluteFill} />
      </Animated.View>

      {/* Ambient light leak */}
      <Animated.View
        style={[
          {
            position: "absolute",
            top: -glowSize * 0.45,
            right: -glowSize * 0.35,
            width: glowSize,
            height: glowSize,
          },
          glowStyle,
        ]}
      >
        <Svg width={glowSize} height={glowSize} viewBox="0 0 100 100">
          <Defs>
            <RadialGradient id="ambientLeak" cx="50%" cy="50%" r="50%">
              <Stop offset="0%" stopColor={glowColor} stopOpacity={1} />
              <Stop offset="55%" stopColor={glowColor} stopOpacity={0.35} />
              <Stop offset="100%" stopColor={glowColor} stopOpacity={0} />
            </RadialGradient>
          </Defs>
          <Circle cx={50} cy={50} r={50} fill="url(#ambientLeak)" />
        </Svg>
      </Animated.View>
    </View>
  );
}
