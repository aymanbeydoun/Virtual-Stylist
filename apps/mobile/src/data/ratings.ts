/**
 * The 1–6 reaction scale users tap to tell the AI how they feel about an
 * outfit — rendered as a geometric tier control (filled diamond segments),
 * not an emoji row.
 */
export interface RatingOption {
  value: number;
  label: string;
}

export const RATINGS: RatingOption[] = [
  { value: 1, label: "Really bad" },
  { value: 2, label: "Bad" },
  { value: 3, label: "Alright" },
  { value: 4, label: "Good" },
  { value: 5, label: "Really good" },
  { value: 6, label: "Fantastic" },
];
