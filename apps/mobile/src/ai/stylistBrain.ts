import type { DemoOutfit } from "@/demo/stylist";
import { useAiBrain } from "@/state/aiBrain";

/**
 * Stella's real AI brain — Claude via the Anthropic Messages API.
 *
 * Uses raw fetch rather than @anthropic-ai/sdk: the official SDK's client
 * statically imports Node built-ins (node:fs and friends for CLI credential
 * files), which Metro cannot resolve in React Native — verified by a failed
 * bundle. React Native's global fetch covers everything we need.
 *
 * Every function degrades gracefully: `null` means "no key or the call
 * failed", and callers fall back to the built-in reply engine so the app
 * always works, even offline.
 */
const API_URL = "https://api.anthropic.com/v1/messages";
const API_VERSION = "2023-06-01";
const MODEL = "claude-opus-4-8";
const TIMEOUT_MS = 30_000;

interface WireTextBlock {
  type: string;
  text?: string;
}

interface WireMessage {
  content: WireTextBlock[];
  stop_reason: string | null;
}

type ChatRole = "user" | "assistant";

async function callClaude(body: {
  system: string;
  messages: { role: ChatRole; content: string }[];
  output_config?: unknown;
}): Promise<WireMessage | null> {
  const apiKey = useAiBrain.getState().apiKey;
  if (!apiKey) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const resp = await fetch(API_URL, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": API_VERSION,
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 1024,
        ...body,
      }),
    });
    if (!resp.ok) {
      throw new Error(`Claude API error ${resp.status}`);
    }
    return (await resp.json()) as WireMessage;
  } finally {
    clearTimeout(timer);
  }
}

function textOf(message: WireMessage): string {
  return message.content
    .filter((b) => b.type === "text" && typeof b.text === "string")
    .map((b) => b.text)
    .join("\n")
    .trim();
}

function stellaSystemPrompt(aiName: string, context?: string): string {
  return [
    `You are ${aiName}, the user's personal AI stylist inside the mobile app STaiLE ME.`,
    "",
    "About the app: the user picks a vibe (Chill, Energetic, Classy, Romantic, Bold, Playful) and an occasion (Mall Day, Beach Day, Dinner Date, Party, Office, Brunch, Gym, Travel, Formal) on the Style tab, taps the STaiLE ME button, and you compose outfits from their closet. They can rate each look on a six-step scale and chat with you here. There is also a Status ladder of 16 ranks (Style Rookie up to Eternal Icon) that grows the more days they use the app.",
    context ? `\nRight now you are chatting about: ${context}.` : "",
    "",
    "You have already greeted the user and asked how their day was.",
    "",
    "How to behave:",
    "- Be warm, playful and encouraging — a stylish best friend, never formal or robotic.",
    "- The user may be young. Keep everything age-appropriate, kind and safe. Never discuss anything inappropriate for kids; steer back to fashion, their day, or fun topics.",
    "- Care about their day. If it was rough, comfort first, style second.",
    "- Keep replies short: one to three sentences per paragraph, at most two short paragraphs. This is a chat bubble, not an essay.",
    "- When they ask to change an outfit (different shoes, less colourful, cosier), agree enthusiastically, say what you'd swap, and remind them to tap the STaiLE ME button on the Style tab to re-generate.",
    "- You may use at most one or two emojis per reply.",
    "- Answer any reasonable general question honestly. If you don't know, say so cheerfully.",
  ].join("\n");
}

/**
 * Ask Claude for Stella's next reply. Returns paragraphs to render as separate
 * chat bubbles, or null when the AI brain is off/unavailable.
 */
export async function chatWithStella(opts: {
  aiName: string;
  context?: string;
  history: { from: "ai" | "user"; text: string }[];
}): Promise<string[] | null> {
  const messages = opts.history.map((m) => ({
    role: m.from === "ai" ? ("assistant" as const) : ("user" as const),
    content: m.text,
  }));
  // The API requires the first message to be from the user; Stella's local
  // greeting opens the chat, so trim leading assistant turns.
  while (messages.length > 0 && messages[0]!.role === "assistant") {
    messages.shift();
  }
  if (messages.length === 0) return null;

  const response = await callClaude({
    system: stellaSystemPrompt(opts.aiName, opts.context),
    messages,
  });
  if (!response) return null;

  if (response.stop_reason === "refusal") {
    return ["Hmm, let's chat about something else — like your next outfit! ✨"];
  }

  const text = textOf(response);
  if (!text) return null;

  // Render paragraphs as separate bubbles, capped so replies stay chat-sized.
  return text.split(/\n{2,}/).slice(0, 3);
}

/**
 * Ask Claude to write personalised "Stella's choice" rationales for freshly
 * generated demo outfits. Returns one string per outfit, or null on failure.
 */
export async function personalizeRationales(opts: {
  aiName: string;
  vibe: string;
  occasion: string;
  outfits: DemoOutfit[];
}): Promise<string[] | null> {
  const looks = opts.outfits
    .map((o, i) => `Outfit ${i + 1}: ${o.items.map((it) => it.name).join(", ")}`)
    .join("\n");

  const response = await callClaude({
    system:
      `You are ${opts.aiName}, a warm personal stylist in the STaiLE ME app. ` +
      "The user may be young — keep it kind and age-appropriate.",
    messages: [
      {
        role: "user",
        content:
          `The user asked for a ${opts.vibe} vibe for a ${opts.occasion}. ` +
          `You composed these looks from their closet:\n${looks}\n\n` +
          "Write one enthusiastic sentence per outfit explaining why it works for that vibe and occasion — mention at least one specific piece by name.",
      },
    ],
    output_config: {
      format: {
        type: "json_schema",
        schema: {
          type: "object",
          properties: {
            rationales: {
              type: "array",
              items: { type: "string" },
              description: "One rationale per outfit, in order.",
            },
          },
          required: ["rationales"],
          additionalProperties: false,
        },
      },
    },
  });
  if (!response || response.stop_reason === "refusal") return null;

  try {
    const parsed = JSON.parse(textOf(response)) as { rationales?: unknown };
    if (!Array.isArray(parsed.rationales)) return null;
    const rationales = parsed.rationales.filter(
      (r): r is string => typeof r === "string" && r.length > 0,
    );
    return rationales.length > 0 ? rationales : null;
  } catch {
    return null;
  }
}
