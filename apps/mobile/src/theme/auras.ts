/**
 * Aura definitions — Project Verve, Pillar 3.
 *
 * An aura is the emotional colour-field of an outfit. When the stylist
 * generates looks, the whole app canvas breathes into the aura's gradient
 * (see ThemeEngine). Gradients stay ink-anchored so the design system's
 * near-black base and neon accents keep punching.
 */
export interface Aura {
  id: string;
  name: string;
  /** Vertical gradient stops, top → bottom. Ink-anchored at the bottom. */
  gradient: [string, string, ...string[]];
  /** Bright tone for the ambient light leak (ThemeEngine layer 2). */
  leak: string;
}

export const AURAS: Record<string, Aura> = {
  chill: {
    id: "chill",
    name: "Dusk",
    gradient: ["#0B1B2E", "#0A1220", "#0A0B0E"],
    leak: "#4D9FFF",
  },
  energetic: {
    id: "energetic",
    name: "Voltage",
    gradient: ["#2E0A1A", "#1E0A14", "#0A0B0E"],
    leak: "#FF2E5F",
  },
  classy: {
    id: "classy",
    name: "Boardroom",
    gradient: ["#1A160A", "#12100C", "#0A0B0E"],
    leak: "#FFC24B",
  },
  romantic: {
    id: "romantic",
    name: "Wine Hour",
    gradient: ["#26081C", "#170A14", "#0A0B0E"],
    leak: "#FF4D8D",
  },
  bold: {
    id: "bold",
    name: "Cyber",
    gradient: ["#160A2E", "#100A1E", "#0A0B0E"],
    leak: "#8B3DFF",
  },
  playful: {
    id: "playful",
    name: "Arcade",
    gradient: ["#082420", "#0A1614", "#0A0B0E"],
    leak: "#22E3B5",
  },
  // Kid-mode vibes reuse the closest adult aura.
  cozy: {
    id: "cozy",
    name: "Dusk",
    gradient: ["#0B1B2E", "#0A1220", "#0A0B0E"],
    leak: "#4D9FFF",
  },
  hero: {
    id: "hero",
    name: "Voltage",
    gradient: ["#2E0A1A", "#1E0A14", "#0A0B0E"],
    leak: "#FF2E5F",
  },
};

export function auraForVibe(vibeId: string): Aura | null {
  return AURAS[vibeId] ?? null;
}
