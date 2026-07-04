/**
 * STaiLE ME design system — "ink & neon" edition.
 *
 * Canvas: a rich near-black ink (#0A0B0E) so accents punch aggressively.
 * Surfaces: glassmorphism — translucent overlays with 1px semi-transparent
 * hairline borders instead of solid card fills.
 * Type: Archivo Black (brutalist display) for headers, Space Grotesk (tight
 * geometric) for labels, data and body copy.
 */
export const palette = {
  /** Ink-toned near-black canvas. */
  background: "#0A0B0E",
  /** Glass card fill — translucent white over ink. */
  surface: "rgba(255,255,255,0.055)",
  /** Slightly stronger glass (pressed states, wells, placeholders). */
  surfaceAlt: "rgba(255,255,255,0.11)",
  /** Solid panel tone for opaque chrome (tab bar, garment backdrops). */
  panel: "#101218",
  /** 1px semi-transparent hairline borders. */
  hairline: "rgba(255,255,255,0.14)",
  /** Fainter hairline for nested separators. */
  hairlineFaint: "rgba(255,255,255,0.07)",
  text: "#F5F6F7",
  textMuted: "#8A8F98",
  accent: "#FF4D8D",
  accentDark: "#D81B60",
  success: "#34D399",
  danger: "#FF5C5C",
  kidPrimary: "#FFC24B",
  kidAccent: "#4D9FFF",
};

/** Loaded in App.tsx via expo-font; referenced everywhere through these keys. */
export const fonts = {
  /** Heavy geometric display — screen headers, brand marks. */
  display: "ArchivoBlack_400Regular",
  /** Tight geometric body. */
  body: "SpaceGrotesk_400Regular",
  bodyMedium: "SpaceGrotesk_500Medium",
  bodyBold: "SpaceGrotesk_700Bold",
  /** Data labels (categories, percentages) — Grotesk with wide tracking. */
  mono: "SpaceGrotesk_500Medium",
};

/** Shared glass-card recipe: translucent fill + 1px hairline. */
export const glass = {
  backgroundColor: palette.surface,
  borderWidth: 1,
  borderColor: palette.hairline,
} as const;

export const radii = { sm: 8, md: 14, lg: 22, pill: 999 };

export const spacing = (n: number) => n * 4;

export type ThemeMode = "adult" | "kid";
