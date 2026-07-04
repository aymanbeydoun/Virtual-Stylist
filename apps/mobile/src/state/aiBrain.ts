import { create } from "zustand";
import { persist } from "zustand/middleware";

import { persistedStorage } from "@/state/persist";

/**
 * Holds the user's Anthropic API key for Stella's real AI brain.
 *
 * The key is entered in the You tab, kept in the device's secure keychain
 * (SecureStore) and used directly from this device only. That's fine for a
 * personal/dev build; a public App Store release would route requests through
 * our backend instead of shipping keys on devices.
 */
interface AiBrainState {
  apiKey: string | null;
  setApiKey: (key: string) => void;
  clearApiKey: () => void;
}

export const useAiBrain = create<AiBrainState>()(
  persist(
    (set) => ({
      apiKey: null,
      setApiKey: (key) => {
        const trimmed = key.trim();
        set({ apiKey: trimmed.length > 0 ? trimmed : null });
      },
      clearApiKey: () => set({ apiKey: null }),
    }),
    { name: "stail_ai_brain", storage: persistedStorage },
  ),
);

/** True when a key is saved and Stella should use her real AI brain. */
export function aiBrainEnabled(): boolean {
  return Boolean(useAiBrain.getState().apiKey);
}
