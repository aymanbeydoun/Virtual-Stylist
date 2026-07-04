import { LinearGradient } from "expo-linear-gradient";
import { StyleSheet } from "react-native";

import { useAccent, useBackgroundDesign } from "@/state/theme";

/**
 * Full-screen themed backdrop rendered once behind the whole app. The chosen
 * background "design" is a vertical gradient; the "Accent glow" design tints
 * the top with the current accent colour.
 */
export function AppBackground() {
  const design = useBackgroundDesign();
  const accent = useAccent();

  const stops = (
    design.fromAccent ? [`${accent.color}55`, "#0F172A", "#020617"] : [...design.colors]
  ) as [string, string, ...string[]];

  return <LinearGradient colors={stops} style={StyleSheet.absoluteFill} />;
}
