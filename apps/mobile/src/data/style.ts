import type { Destination, Mood } from "@/api/types";

/**
 * User-facing "vibe" and "occasion" choices. The backend only accepts a fixed
 * set of `Mood` / `Destination` enum values, so each friendly option maps onto
 * the nearest supported value. The original friendly label is still sent to the
 * stylist via free-text notes so the rationale can reference it.
 */

export interface VibeOption {
  id: string;
  label: string;
  emoji: string;
  mood: Mood;
}

export interface OccasionOption {
  id: string;
  label: string;
  emoji: string;
  destination: Destination;
}

export const VIBES: VibeOption[] = [
  { id: "chill", label: "Chill", emoji: "😌", mood: "cozy" },
  { id: "loud", label: "Loud", emoji: "🔊", mood: "confident" },
  { id: "classy", label: "Classy", emoji: "🕶️", mood: "minimal" },
  { id: "romantic", label: "Romantic", emoji: "💕", mood: "romantic" },
  { id: "bold", label: "Bold", emoji: "⚡", mood: "edgy" },
  { id: "playful", label: "Playful", emoji: "✨", mood: "playful" },
];

export const OCCASIONS: OccasionOption[] = [
  { id: "mall", label: "Mall Day", emoji: "🛍️", destination: "casual" },
  { id: "beach", label: "Beach Day", emoji: "🏖️", destination: "travel" },
  { id: "dinner", label: "Dinner Date", emoji: "🍽️", destination: "date" },
  { id: "party", label: "Party", emoji: "🥳", destination: "date" },
  { id: "office", label: "Office", emoji: "💼", destination: "office" },
  { id: "brunch", label: "Brunch", emoji: "🥂", destination: "brunch" },
  { id: "gym", label: "Gym", emoji: "🏋️", destination: "gym" },
  { id: "travel", label: "Travel", emoji: "✈️", destination: "travel" },
  { id: "formal", label: "Formal", emoji: "🎩", destination: "formal_event" },
];

export const KID_VIBES: VibeOption[] = [
  { id: "playful", label: "Playful", emoji: "🎉", mood: "playful" },
  { id: "cozy", label: "Cozy", emoji: "🧸", mood: "cozy" },
  { id: "hero", label: "Hero", emoji: "🦸", mood: "confident" },
];

export const KID_OCCASIONS: OccasionOption[] = [
  { id: "school", label: "School", emoji: "🎒", destination: "school" },
  { id: "playground", label: "Playground", emoji: "🛝", destination: "playground" },
  { id: "hangout", label: "Hanging out", emoji: "🙂", destination: "casual" },
];
