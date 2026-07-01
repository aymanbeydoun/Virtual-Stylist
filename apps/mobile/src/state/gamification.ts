import { create } from "zustand";
import { persist } from "zustand/middleware";

import { persistedStorage } from "@/state/persist";

/** Local date as YYYY-MM-DD (used to count one visit per calendar day). */
function todayKey(): string {
  const d = new Date();
  const m = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

interface GamificationState {
  /** Number of distinct calendar days the app has been opened. Drives level. */
  daysUsed: number;
  /** The last day (YYYY-MM-DD) a visit was counted. */
  lastActiveDate: string | null;
  /** Call once per app open; increments the streak at most once per day. */
  registerVisit: () => void;
  reset: () => void;
}

export const useGamification = create<GamificationState>()(
  persist(
    (set, get) => ({
      daysUsed: 0,
      lastActiveDate: null,
      registerVisit: () => {
        const today = todayKey();
        if (get().lastActiveDate === today) return;
        set((s) => ({ daysUsed: s.daysUsed + 1, lastActiveDate: today }));
      },
      reset: () => set({ daysUsed: 0, lastActiveDate: null }),
    }),
    { name: "stail_gamification", storage: persistedStorage },
  ),
);
