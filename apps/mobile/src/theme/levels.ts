/**
 * The STaiLE ME status ladder.
 *
 * Levels are unlocked purely by how many distinct days a user has opened the
 * app (their streak of engagement). Each level has a distinct colour and a
 * bespoke geometric insignia (see LevelInsignia) so the ladder reads as a
 * collectible progression.
 *
 * `minDays` is the number of days-used required to reach the level. The
 * `timeReached` label is the human-friendly wording shown on the status ladder.
 */
export interface StyleLevel {
  level: number;
  title: string;
  timeReached: string;
  /** Days of usage required to reach the level. */
  minDays: number;
  /** Signature colour for the insignia / row. */
  color: string;
}

// Colours form one smooth sweep through the spectrum so adjacent levels are
// always the closest shades: blue → cyan → green → lime → gold → orange →
// red → pink → magenta → purple → violet.
export const LEVELS: StyleLevel[] = [
  { level: 1, title: "Style Rookie", timeReached: "1 Day", minDays: 1, color: "#38BDF8" },
  { level: 2, title: "Fit Explorer", timeReached: "1 Week", minDays: 7, color: "#22D3EE" },
  { level: 3, title: "Trend Seeker", timeReached: "1 Month", minDays: 30, color: "#2DD4BF" },
  { level: 4, title: "Style Builder", timeReached: "2 Months", minDays: 60, color: "#34D399" },
  { level: 5, title: "Outfit Architect", timeReached: "3 Months", minDays: 90, color: "#4ADE80" },
  { level: 6, title: "Outfit Talent", timeReached: "4 Months", minDays: 120, color: "#A3E635" },
  { level: 7, title: "Fashion Strategist", timeReached: "5 Months", minDays: 150, color: "#FACC15" },
  { level: 8, title: "Clothing Developer", timeReached: "6 Months", minDays: 180, color: "#FBBF24" },
  { level: 9, title: "Style Influencer", timeReached: "7 Months", minDays: 210, color: "#FB923C" },
  { level: 10, title: "Trend Controller", timeReached: "8 Months", minDays: 240, color: "#F97316" },
  { level: 11, title: "Luxury Mindset", timeReached: "9 Months", minDays: 270, color: "#F87171" },
  { level: 12, title: "Elite Stylist", timeReached: "10 Months", minDays: 300, color: "#F43F5E" },
  { level: 13, title: "Fashion Visionary", timeReached: "11 Months", minDays: 330, color: "#EC4899" },
  { level: 14, title: "Cultural Trendsetter", timeReached: "12 Months", minDays: 360, color: "#D946EF" },
  { level: 15, title: "Fashion Immortal", timeReached: "1 Year", minDays: 365, color: "#A855F7" },
  { level: 16, title: "Eternal Icon", timeReached: "1 Year+", minDays: 366, color: "#8B5CF6" },
];

/** The highest level whose `minDays` threshold the user has met. */
export function levelForDays(daysUsed: number): StyleLevel {
  let current: StyleLevel = LEVELS[0]!;
  for (const lvl of LEVELS) {
    if (daysUsed >= lvl.minDays) {
      current = lvl;
    }
  }
  return current;
}

/** The next level to aim for, or null if already at the top. */
export function nextLevel(daysUsed: number): StyleLevel | null {
  return LEVELS.find((lvl) => daysUsed < lvl.minDays) ?? null;
}
