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

/** The palette the user can pick from — black stays; the accent changes. */
export const ACCENT_THEMES: AccentTheme[] = [
  { id: "pink", name: "Pink", color: "#F472B6", dark: "#DB2777" },
  { id: "red", name: "Red", color: "#FB7185", dark: "#E11D48" },
  { id: "orange", name: "Orange", color: "#FB923C", dark: "#EA580C" },
  { id: "yellow", name: "Yellow", color: "#FACC15", dark: "#CA8A04" },
  { id: "lime", name: "Lime", color: "#A3E635", dark: "#65A30D" },
  { id: "green", name: "Green", color: "#34D399", dark: "#059669" },
  { id: "teal", name: "Teal", color: "#2DD4BF", dark: "#0D9488" },
  { id: "cyan", name: "Cyan", color: "#22D3EE", dark: "#0891B2" },
  { id: "blue", name: "Blue", color: "#60A5FA", dark: "#2563EB" },
  { id: "indigo", name: "Indigo", color: "#818CF8", dark: "#4F46E5" },
  { id: "purple", name: "Purple", color: "#C084FC", dark: "#9333EA" },
  { id: "magenta", name: "Magenta", color: "#E879F9", dark: "#C026D3" },
];

interface ThemeState {
  accentId: string;
  setAccent: (id: string) => void;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      accentId: "pink",
      setAccent: (id) => set({ accentId: id }),
    }),
    { name: "stail_theme", storage: persistedStorage },
  ),
);

/** Hook returning the currently selected accent theme object. */
export function useAccent(): AccentTheme {
  const id = useTheme((s) => s.accentId);
  return ACCENT_THEMES.find((t) => t.id === id) ?? ACCENT_THEMES[0]!;
}
