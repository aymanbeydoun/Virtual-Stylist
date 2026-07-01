/**
 * The 1–6 reaction scale users tap to tell the AI how they feel about an
 * outfit, from "really bad" up to "fantastic".
 */
export interface RatingOption {
  value: number;
  emoji: string;
  label: string;
}

export const RATINGS: RatingOption[] = [
  { value: 1, emoji: "😖", label: "Really bad" },
  { value: 2, emoji: "🙁", label: "Bad" },
  { value: 3, emoji: "😐", label: "Alright" },
  { value: 4, emoji: "🙂", label: "Good" },
  { value: 5, emoji: "😄", label: "Really good" },
  { value: 6, emoji: "🤩", label: "Fantastic" },
];
