/**
 * The Stail Me status ladder.
 *
 * Levels are unlocked purely by how many distinct days a user has opened the
 * app (their streak of engagement). Each level has a distinct "cool" colour so
 * the badge and the status screen feel like a collectible progression.
 *
 * `minDays` is the number of days-used required to reach the level. The
 * `timeReached` label is the human-friendly wording shown on the status ladder.
 */
export interface StyleLevel {
  level: number;
  title: string;
  timeReached: string;
  /** Days of usage required to unlock this level. */
  minDays: number;
  /** Signature colour for the badge / row. */
  color: string;
  /** A small flair emoji shown next to the title. */
  emoji: string;
}

export const LEVELS: StyleLevel[] = [
  { level: 1, title: "Style Rookie", timeReached: "1 Day", minDays: 1, color: "#8FA3B8", emoji: "🌱" },
  { level: 2, title: "Fit Explorer", timeReached: "1 Week", minDays: 7, color: "#4CC9F0", emoji: "🧭" },
  { level: 3, title: "Trend Seeker", timeReached: "1 Month", minDays: 30, color: "#22D3EE", emoji: "🔭" },
  { level: 4, title: "Style Builder", timeReached: "2 Months", minDays: 60, color: "#2DD4BF", emoji: "🧱" },
  { level: 5, title: "Outfit Architect", timeReached: "3 Months", minDays: 90, color: "#34D399", emoji: "📐" },
  { level: 6, title: "Outfit Talent", timeReached: "4 Months", minDays: 120, color: "#A3E635", emoji: "🎯" },
  { level: 7, title: "Fashion Strategist", timeReached: "5 Months", minDays: 150, color: "#FACC15", emoji: "♟️" },
  { level: 8, title: "Clothing Developer", timeReached: "6 Months", minDays: 180, color: "#FB923C", emoji: "🛠️" },
  { level: 9, title: "Style Influencer", timeReached: "7 Months", minDays: 210, color: "#F472B6", emoji: "📣" },
  { level: 10, title: "Trend Controller", timeReached: "8 Months", minDays: 240, color: "#E879F9", emoji: "🎛️" },
  { level: 11, title: "Luxury Mindset", timeReached: "9 Months", minDays: 270, color: "#C084FC", emoji: "💎" },
  { level: 12, title: "Elite Stylist", timeReached: "10 Months", minDays: 300, color: "#A78BFA", emoji: "👑" },
  { level: 13, title: "Fashion Visionary", timeReached: "11 Months", minDays: 330, color: "#818CF8", emoji: "🔮" },
  { level: 14, title: "Cultural Trendsetter", timeReached: "12 Months", minDays: 360, color: "#60A5FA", emoji: "🌍" },
  { level: 15, title: "Fashion Immortal", timeReached: "1 Year", minDays: 365, color: "#FCD34D", emoji: "⭐" },
  { level: 16, title: "Eternal Icon", timeReached: "1 Year+", minDays: 366, color: "#FF3D7F", emoji: "🏆" },
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
