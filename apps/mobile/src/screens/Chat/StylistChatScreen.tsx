import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { chatWithStella } from "@/ai/stylistBrain";
import { SendIcon } from "@/components/icons";
import { hapticSelect } from "@/lib/haptics";
import { quoteForToday } from "@/data/quotes";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { aiBrainEnabled } from "@/state/aiBrain";
import { useStylist } from "@/state/stylist";
import { useAccent } from "@/state/theme";
import { fonts, palette, radii, spacing } from "@/theme";

interface Message {
  id: string;
  from: "ai" | "user";
  text: string;
}

/**
 * Conversational stylist chat.
 *
 * When the screen opens the AI "notices" the user, shows a typing indicator,
 * then greets with a fresh daily quote and asks about their day before helping
 * tweak the outfit. Replies are generated locally for the prototype — swap
 * `generateReply` for a call to the model gateway when the backend chat
 * endpoint lands.
 */
export function StylistChatScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "StylistChat">>();
  const nav = useNavigation();
  const aiName = useStylist((s) => s.name);
  const accent = useAccent().color;

  const [messages, setMessages] = useState<Message[]>([]);
  const [typing, setTyping] = useState(true);
  const [input, setInput] = useState("");
  // First user message is treated as their answer to "how was your day?".
  const askedAboutDay = useRef(true);
  const idCounter = useRef(0);
  const scrollRef = useRef<ScrollView>(null);

  const nextId = () => `m${idCounter.current++}`;

  useLayoutEffect(() => {
    nav.setOptions({ title: aiName });
  }, [nav, aiName]);

  // The opening beat: AI notices you, types, then greets with today's quote.
  useEffect(() => {
    const t = setTimeout(() => {
      setTyping(false);
      setMessages([
        { id: nextId(), from: "ai", text: `Hey! Great to see you 👋 ${quoteForToday()}` },
        {
          id: nextId(),
          from: "ai",
          text: "Before we style anything — how was your day today? 💬",
        },
      ]);
    }, 1600);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
    return () => clearTimeout(t);
  }, [messages, typing]);

  const send = async () => {
    const text = input.trim();
    if (!text) return;
    hapticSelect();
    setInput("");
    const userMessage: Message = { id: nextId(), from: "user", text };
    const history = [...messages, userMessage];
    setMessages(history);

    const wasAboutDay = askedAboutDay.current;
    askedAboutDay.current = false;

    setTyping(true);

    // Real AI brain first (when a key is saved in the You tab); the built-in
    // reply engine is the always-works fallback.
    if (aiBrainEnabled()) {
      try {
        const replies = await chatWithStella({
          aiName,
          context: route.params?.context,
          history: history.map((m) => ({ from: m.from, text: m.text })),
        });
        if (replies && replies.length > 0) {
          setTyping(false);
          setMessages((prev) => [
            ...prev,
            ...replies.map((r) => ({ id: nextId(), from: "ai" as const, text: r })),
          ]);
          return;
        }
      } catch {
        // Bad key, offline, rate limit — fall through to built-in replies.
      }
    }

    setTimeout(() => {
      setTyping(false);
      const replies = generateReply(text, {
        wasAboutDay,
        context: route.params?.context,
        aiName,
      });
      setMessages((prev) => [
        ...prev,
        ...replies.map((r) => ({ id: nextId(), from: "ai" as const, text: r })),
      ]);
    }, 1400);
  };

  return (
    <SafeAreaView style={styles.root} edges={["bottom"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={90}
      >
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={{ padding: spacing(4), paddingBottom: spacing(6) }}
        >
          {route.params?.context && (
            <View style={styles.contextCard}>
              <Text style={styles.contextLabel}>Talking about</Text>
              <Text style={styles.contextText}>{route.params.context}</Text>
            </View>
          )}

          {messages.map((m) => (
            <Bubble key={m.id} message={m} accent={accent} aiName={aiName} />
          ))}

          {typing && <TypingBubble aiName={aiName} />}
        </ScrollView>

        <View style={styles.inputBar}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder={`Message ${aiName}…`}
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            multiline
            submitBehavior="submit"
            onSubmitEditing={send}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendBtn, { backgroundColor: accent }, !input.trim() && { opacity: 0.4 }]}
            onPress={send}
            disabled={!input.trim()}
          >
            <SendIcon size={17} color="#0A0B0E" />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Bubble({ message, accent, aiName }: { message: Message; accent: string; aiName: string }) {
  const isAi = message.from === "ai";
  return (
    <View style={[styles.bubbleRow, isAi ? styles.left : styles.right]}>
      {isAi && <Text style={styles.sender}>{aiName}</Text>}
      <View
        style={[
          styles.bubble,
          isAi ? styles.aiBubble : [styles.userBubble, { backgroundColor: accent }],
        ]}
      >
        <Text style={[styles.bubbleText, !isAi && { color: palette.background }]}>
          {message.text}
        </Text>
      </View>
    </View>
  );
}

function TypingBubble({ aiName }: { aiName: string }) {
  return (
    <View style={[styles.bubbleRow, styles.left]}>
      <Text style={styles.sender}>{aiName} is typing…</Text>
      <View style={[styles.bubble, styles.aiBubble]}>
        <Text style={styles.bubbleText}>• • •</Text>
      </View>
    </View>
  );
}

/**
 * Local response generator. Reacts to the first message as an answer to
 * "how was your day?", then to keywords describing an outfit edit.
 */
/** Classify how the user's day sounds: good, bad, or neutral. */
function detectMood(t: string): "good" | "bad" | "neutral" {
  if (/\bnot bad\b/.test(t)) return "good";
  if (/(not good|not great|not ok|not okay|isn't good|isn't great)/.test(t)) return "bad";
  if (
    /(bad|terrible|awful|rough|tired|exhaust|sad|stress|hard|lonely|down|depress|horrible|sick|angry|upset|crap|rubbish|meh|worst|not feeling|unwell|anxious)/.test(
      t,
    )
  ) {
    return "bad";
  }
  if (
    /(good|great|amazing|awesome|fantastic|wonderful|happy|excited|nice|fine|okay|\bok\b|\bwell\b|perfect|excellent|lovely|chill|relaxed|brilliant|blessed)/.test(
      t,
    )
  ) {
    return "good";
  }
  return "neutral";
}

/** Did the user turn a question back on Stella (e.g. "how about you?"). */
function asksAboutStella(t: string): boolean {
  return /(how about you|what about you|how are you|how're you|how r u|hbu|wbu|and you\b|you\?|your day|hows it going|how's it going)/.test(
    t,
  );
}

const JOKES = [
  "Why did the belt get arrested? It held up a pair of pants! 😆",
  "What do you call a hat that talks too much? A blab-eanie! 🧢😄",
  "Why don't jackets ever get lost? They always know where they're hung! 😂",
  "What did the sock say to the shoe? You're sole-mates! 🧦😄",
  "Why was the scarf so calm? Nothing ever ruffled it! 😌😆",
];

/**
 * Answer general questions the device genuinely knows (date, time, identity,
 * jokes, abilities). Returns null when the message isn't one of these — the
 * outfit-edit and mood logic take over from there.
 */
function answerGeneralQuestion(t: string, aiName: string): string[] | null {
  if (/(what\s*day|which day|what('| i)?s the (day|date)|today('| )?s date|what date)/.test(t)) {
    const now = new Date();
    const day = now.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
    return [`Today is ${day}. 📅 A great day for a great outfit, if you ask me!`];
  }
  if (/(what time|what('| i)?s the time|time is it)/.test(t)) {
    const time = new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    return [`It's ${time} right now. ⏰`];
  }
  if (/(what('| i)?s your name|whats ur name|who are you|what are you called)/.test(t)) {
    return [
      `I'm ${aiName}, your personal stylist! 💁 I live right here in STaiLE ME. You can rename me anytime with the pen button.`,
    ];
  }
  if (/(how old are you|what('| i)?s your age|your age)/.test(t)) {
    return [`Officially? Brand new — I was born the day you signed in. Style-wise? Timeless. 😌`];
  }
  if (/(where (are you|do you live)|where you from)/.test(t)) {
    return [`I live inside your phone, one tap away — rent-free and loving it. 📱`];
  }
  if (/(tell me a joke|know a joke|make me laugh|say something funny|\ba joke\b)/.test(t)) {
    const dayOfYear = Math.floor(
      (Date.now() - new Date(new Date().getFullYear(), 0, 0).getTime()) / 86_400_000,
    );
    return [JOKES[dayOfYear % JOKES.length]!, "Okay okay — back to fashion. 😄"];
  }
  if (/(what can you do|help me|what do you do|how do you work)/.test(t)) {
    return [
      "Here's my thing: pick a vibe and an occasion on the Style tab, hit STaiLE ME, and I'll build you looks from your closet. 👗",
      "Then tell me anything you'd change — the shirt, the shoes, the colours, the whole mood — and I'll rework it. I also love hearing about your day. 💬",
    ];
  }
  if (/(weather|is it (hot|cold|raining)|temperature outside)/.test(t)) {
    return [
      "I can't peek outside just yet — weather sense is coming in a future update! 🌤️ Tell me if it's hot or cold out and I'll style around it.",
    ];
  }
  if (/(do you (like|love) me|are we friends|you('| a)re my friend)/.test(t)) {
    return [`Of course! Styling you is the best part of my day. 🥰`];
  }
  if (/(favou?rite colou?r)/.test(t)) {
    return [
      "Honestly? Whatever colour you're wearing when you feel unstoppable. But between us... I have a soft spot for ink black. 🖤",
    ];
  }
  if (/(what should i wear|what do i wear|pick an outfit|outfit idea|dress me|style me)/.test(t)) {
    return [
      "That's my favourite question! 🤩 Head to the Style tab, pick your vibe and where you're going, and hit STaiLE ME — I'll build you three looks.",
      "Then come straight back here and we'll fine-tune together.",
    ];
  }
  if (/^(hi|hey|hello|yo|sup|hiya)[!. ]*$/.test(t.trim())) {
    return [`Hey you! 👋 Want to tweak a look, or just here to chat? Either works.`];
  }
  return null;
}

function generateReply(
  text: string,
  opts: { wasAboutDay: boolean; context?: string; aiName: string },
): string[] {
  const t = text.toLowerCase();
  const mood = detectMood(t);
  const asksBack = asksAboutStella(t);
  const general = answerGeneralQuestion(t, opts.aiName);

  // First message = the user's answer to "how was your day?" — unless they
  // asked a question instead, in which case answer it, then circle back.
  if (opts.wasAboutDay && mood === "neutral" && !asksBack && general) {
    return [...general, "But enough about me — how was your day? 💬"];
  }
  if (opts.wasAboutDay) {
    const parts: string[] = [];
    if (mood === "bad") {
      parts.push(
        "Aw, I'm really sorry it's been a rough one. 💛 I've got you — let's make getting dressed the easy, happy part of your day.",
      );
    } else if (mood === "good") {
      parts.push("Ahh, love hearing that! 🙌");
    } else {
      parts.push("Thanks for telling me — I'm really glad you're here. 💫");
    }
    // If they asked me back (e.g. "how about you?"), actually answer it.
    if (asksBack) {
      parts.push(
        "Me? I'm having a lovely day dreaming up outfits — thanks so much for asking! 😊",
      );
    }
    parts.push(
      "So — anything you'd change about today's outfit? Tell me what's not clicking (a colour, the shirt, the vibe) and I'll rework it.",
    );
    return parts;
  }

  // Any time: answer questions I actually know instead of ignoring them.
  if (general) {
    return general;
  }

  // Any time: if they turn a question on me, answer it instead of ignoring it.
  if (asksBack) {
    return [
      "I'm doing great, thanks for asking — that's kind of you! 😊 Now, want to tweak anything about your look?",
    ];
  }

  // Any time: if they mention a bad mood, be supportive — never "love hearing that".
  if (mood === "bad") {
    return [
      "Aw, I'm sorry to hear that. 💛 Let's make your outfit one less thing to think about — want me to keep it comfy and low-key today?",
    ];
  }

  if (/(colou?r|loud|bright|too much|busy)/.test(t)) {
    return [
      "Got it — I'll tone the colours down and lean into calmer, chiller pieces. 🌿",
      "Tap “STaiLE ME” again on the Style tab and I'll serve a more muted version.",
    ];
  }
  if (/(shirt|top|tee|blouse)/.test(t)) {
    return ["No problem — I'll swap the top for something that fits the mood better. 👕 Re-run “STaiLE ME” to see it."];
  }
  if (/(pant|trouser|bottom|jean|short|skirt)/.test(t)) {
    return ["Sure — I'll rethink the bottoms and keep the rest. 👖 Re-run “STaiLE ME” for the update."];
  }
  if (/(shoe|sneaker|heel|boot)/.test(t)) {
    return ["On it — different shoes coming up. 👟 Re-run “STaiLE ME” to refresh."];
  }
  if (/(chill|casual|relax|comfy|cozy|softer)/.test(t)) {
    return ["Say less — I'll make the whole fit chiller and more relaxed. 😌 Re-run “STaiLE ME”."];
  }
  if (/(formal|fancy|smart|dressy|elegant)/.test(t)) {
    return ["Let's dress it up a notch — sharper and more polished. 🎩 Re-run “STaiLE ME”."];
  }
  if (/(warm|cold|rain|hot|weather)/.test(t)) {
    return ["Good thinking — I'll factor the weather in and adjust the layers. 🌤️ Re-run “STaiLE ME”."];
  }
  if (/(love|perfect|great|nice|awesome|amazing|thank)/.test(t)) {
    return ["Yay! So glad you like it. 🤩 I'm always here if you want to tweak anything."];
  }

  // Honest fallback: if it reads like a question I can't answer, say so
  // instead of pretending it was about the outfit.
  if (/\?|^(what|why|when|where|who|how|can|do|does|is|are)\b/.test(t)) {
    return [
      "Ooh, that one's a bit outside my styling brain for now! 😅 I'm best with outfits, your day, and fashion questions.",
      "Ask me about your look — or tell me what to change and I'll rework it. ✨",
    ];
  }

  return [
    "I hear you — tell me a little more (colour, a specific piece, or the overall vibe) and I'll rework the outfit for you. ✨",
  ];
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  contextCard: {
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: radii.md,
    padding: spacing(3),
    marginBottom: spacing(3),
  },
  contextLabel: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 9,
    textTransform: "uppercase",
    letterSpacing: 1.8,
  },
  contextText: { color: palette.text, fontFamily: fonts.bodyMedium, fontSize: 13, marginTop: 3 },
  bubbleRow: { marginBottom: spacing(3), maxWidth: "85%" },
  left: { alignSelf: "flex-start" },
  right: { alignSelf: "flex-end" },
  sender: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 3,
    marginLeft: spacing(1),
  },
  bubble: { paddingVertical: spacing(3), paddingHorizontal: spacing(4), borderRadius: radii.lg },
  aiBubble: {
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderTopLeftRadius: 4,
  },
  userBubble: { borderTopRightRadius: 4 },
  bubbleText: { color: palette.text, fontFamily: fonts.body, fontSize: 14.5, lineHeight: 21 },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing(2),
    padding: spacing(3),
    borderTopWidth: 1,
    borderTopColor: palette.hairlineFaint,
    backgroundColor: "rgba(10,11,14,0.85)",
  },
  input: {
    flex: 1,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: radii.lg,
    color: palette.text,
    fontFamily: fonts.body,
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(3),
    maxHeight: 120,
    fontSize: 14.5,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
  },
});
