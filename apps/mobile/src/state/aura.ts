import { create } from "zustand";

import type { Aura } from "@/theme/auras";

/**
 * The live aura — set when the stylist generates looks, cleared on sign-out.
 * Deliberately NOT persisted: the app should wake up calm (base backdrop)
 * and come alive as you style.
 */
interface AuraState {
  aura: Aura | null;
  setAura: (aura: Aura | null) => void;
}

export const useAura = create<AuraState>((set) => ({
  aura: null,
  setAura: (aura) => set({ aura }),
}));
