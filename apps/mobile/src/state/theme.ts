import { create } from "zustand";
import { persist } from "zustand/middleware";

import { persistedStorage } from "@/state/persist";

export interface AccentTheme {
  id: string;
  name: string;
  /** Main accent colour (buttons, highlights). */
  color: string;
  /** A slightly deeper shade for pressed/secondary states. */
  dark: string;
}

/**
 * Global accent tokens — muted, sophisticated neons plus high-saturation
 * contrast accents (vivid crimson, absolute white, electric blue). The ink
 * canvas never changes; only these high-contrast elements shift.
 */
export const ACCENT_THEMES: AccentTheme[] = [
  { id: "rose", name: "Rose", color: "#FF4D8D", dark: "#D81B60" },
  { id: "crimson", name: "Crimson", color: "#FF2E4D", dark: "#C81E3A" },
  { id: "white", name: "White", color: "#FFFFFF", dark: "#C9CDD4" },
  { id: "electric", name: "Electric", color: "#2E6BFF", dark: "#1D4ED8" },
  { id: "cyan", name: "Cyan", color: "#45E3FF", dark: "#0891B2" },
  { id: "mint", name: "Mint", color: "#34F5C5", dark: "#0D9488" },
  { id: "volt", name: "Volt", color: "#D4FF4F", dark: "#84CC16" },
  { id: "amber", name: "Amber", color: "#FFC24B", dark: "#D97706" },
  { id: "signal", name: "Signal", color: "#FF7847", dark: "#EA580C" },
  { id: "violet", name: "Violet", color: "#9D6BFF", dark: "#7C3AED" },
  { id: "magenta", name: "Magenta", color: "#FF4DD8", dark: "#C026D3" },
  { id: "silver", name: "Silver", color: "#A9B1BD", dark: "#6B7280" },
];

export interface BackgroundDesign {
  id: string;
  name: string;
  /** Gradient stops, top → bottom. Empty when the design is built from the accent. */
  colors: readonly string[];
  /** When true, the gradient is tinted with the current accent colour. */
  fromAccent?: boolean;
}

/** Background "designs" — deep ink undertones; the canvas stays near-black. */
export const BACKGROUND_DESIGNS: BackgroundDesign[] = [
  { id: "solid", name: "Ink", colors: ["#0A0B0E", "#0A0B0E"] },
  { id: "night", name: "Night", colors: ["#060709", "#0A0B0E", "#14122B"] },
  { id: "ocean", name: "Ocean", colors: ["#060709", "#0A1622", "#0A3644"] },
  { id: "sunset", name: "Sunset", colors: ["#0A0B0E", "#26082E", "#3D0E27"] },
  { id: "forest", name: "Forest", colors: ["#061410", "#0A0B0E", "#07200F"] },
  { id: "glow", name: "Accent glow", colors: [], fromAccent: true },
];

interface ThemeState {
  accentId: string;
  backgroundId: string;
  setAccent: (id: string) => void;
  setBackground: (id: string) => void;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      accentId: "pink",
      backgroundId: "solid",
      setAccent: (id) => set({ accentId: id }),
      setBackground: (id) => set({ backgroundId: id }),
    }),
    { name: "stail_theme", storage: persistedStorage },
  ),
);

/** Hook returning the currently selected accent theme object. */
export function useAccent(): AccentTheme {
  const id = useTheme((s) => s.accentId);
  return ACCENT_THEMES.find((t) => t.id === id) ?? ACCENT_THEMES[0]!;
}

/** Hook returning the currently selected background design. */
export function useBackgroundDesign(): BackgroundDesign {
  const id = useTheme((s) => s.backgroundId);
  return BACKGROUND_DESIGNS.find((d) => d.id === id) ?? BACKGROUND_DESIGNS[0]!;
}
