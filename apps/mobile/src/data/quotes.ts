/**
 * A pool of warm, encouraging quotes. The chat greeting shows a *different* one
 * each day (indexed by the day-of-year) so opening the chat feels fresh and
 * personal rather than repetitive.
 */
export const DAILY_QUOTES: string[] = [
  "Style is a way to say who you are without having to speak. 💬",
  "You don't find your look — you create it. ✨",
  "Confidence is the best outfit. Rock it and own it. 💪",
  "Every day is a runway if you walk it like one. 🚶",
  "Dress like you're already famous. 🌟",
  "The joy is in the mix — a little bold, a little you. 🎨",
  "Great style is 10% clothes and 90% attitude. 😎",
  "Wear the outfit. Don't let the outfit wear you. 👗",
  "Comfort and confidence never go out of fashion. 🧡",
  "Life isn't perfect, but your outfit can be close. 💫",
  "Be a voice, not an echo — and dress like it. 🔊",
  "Fashion fades, but your personal style is forever. ♾️",
  "Look good, feel good, do good today. 🌈",
  "A smile is the prettiest thing you can wear. 😊",
  "Today's a clean slate — let's make it a good-looking one. 🧼",
  "Simplicity is the ultimate form of cool. ⚪",
  "Colours are the smiles of nature — wear a few. 🌸",
  "You've got this. And you look great while doing it. 🙌",
  "Small steps, sharp style — one day at a time. 👣",
  "Your vibe attracts your tribe. Let's set the vibe. 🌀",
  "Elegance is when the inside is as beautiful as the outside. 💖",
  "Take up space. Wear what makes you feel like you. 🌻",
  "A new day, a new fit, a new chapter. 📖",
  "Trust the process — and trust your closet. 🔑",
  "Be fearless in the pursuit of what sets your soul on fire. 🔥",
  "You are enough, exactly as you are — the outfit's just the bonus. 💝",
  "Turn the page and dress the part you want. 🎭",
  "The best accessory is a good mood. 🥰",
  "Make today so awesome yesterday gets jealous. ⚡",
  "Own the day like it owes you something. 💼",
];

/** Deterministically pick a quote for today based on the day of the year. */
export function quoteForToday(): string {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const dayOfYear = Math.floor((now.getTime() - start.getTime()) / 86_400_000);
  return DAILY_QUOTES[dayOfYear % DAILY_QUOTES.length]!;
}
