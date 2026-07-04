import type { Destination, Mood } from "@/api/types";

/**
 * User-facing "vibe" and "occasion" choices. The backend only accepts a fixed
 * set of `Mood` / `Destination` enum values, so each friendly option maps onto
 * the nearest supported value. Chips render clean typography only — no native
 * emojis (see the STaiLE ME design system).
 */

export interface VibeOption {
  id: string;
  label: string;
  mood: Mood;
}

export interface OccasionOption {
  id: string;
  label: string;
  destination: Destination;
}

export const VIBES: VibeOption[] = [
  { id: "chill", label: "Chill", mood: "cozy" },
  { id: "energetic", label: "Energetic", mood: "confident" },
  { id: "classy", label: "Classy", mood: "minimal" },
  { id: "romantic", label: "Romantic", mood: "romantic" },
  { id: "bold", label: "Bold", mood: "edgy" },
  { id: "playful", label: "Playful", mood: "playful" },
];

export const OCCASIONS: OccasionOption[] = [
  { id: "mall", label: "Mall Day", destination: "casual" },
  { id: "beach", label: "Beach Day", destination: "travel" },
  { id: "dinner", label: "Dinner Date", destination: "date" },
  { id: "party", label: "Party", destination: "date" },
  { id: "office", label: "Office", destination: "office" },
  { id: "brunch", label: "Brunch", destination: "brunch" },
  { id: "gym", label: "Gym", destination: "gym" },
  { id: "travel", label: "Travel", destination: "travel" },
  { id: "formal", label: "Formal", destination: "formal_event" },
];

export const KID_VIBES: VibeOption[] = [
  { id: "playful", label: "Playful", mood: "playful" },
  { id: "cozy", label: "Cozy", mood: "cozy" },
  { id: "hero", label: "Hero", mood: "confident" },
];

export const KID_OCCASIONS: OccasionOption[] = [
  { id: "school", label: "School", destination: "school" },
  { id: "playground", label: "Playground", destination: "playground" },
  { id: "hangout", label: "Hanging out", destination: "casual" },
];
