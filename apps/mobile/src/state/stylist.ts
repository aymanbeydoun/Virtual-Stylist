import { create } from "zustand";
import { persist } from "zustand/middleware";

import { persistedStorage } from "@/state/persist";

export const DEFAULT_STYLIST_NAME = "Stella";

interface StylistState {
  /** The user-chosen name for their AI stylist. */
  name: string;
  setName: (name: string) => void;
}

/**
 * Holds the (renameable) identity of the AI stylist. Persisted so the chosen
 * name survives restarts.
 */
export const useStylist = create<StylistState>()(
  persist(
    (set) => ({
      name: DEFAULT_STYLIST_NAME,
      setName: (name) => {
        const trimmed = name.trim();
        set({ name: trimmed.length > 0 ? trimmed : DEFAULT_STYLIST_NAME });
      },
    }),
    { name: "stail_stylist", storage: persistedStorage },
  ),
);
