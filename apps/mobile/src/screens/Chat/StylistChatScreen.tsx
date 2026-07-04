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

import { quoteForToday } from "@/data/quotes";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useStylist } from "@/state/stylist";
import { useAccent } from "@/state/theme";
import { palette, radii, spacing } from "@/theme";

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

  const send = () => {
    const text = input.trim();
    if (!text) return;
    setInput("");
    setMessages((prev) => [...prev, { id: nextId(), from: "user", text }]);

    const wasAboutDay = askedAboutDay.current;
    askedAboutDay.current = false;

    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      const replies = generateReply(text, { wasAboutDay, context: route.params?.context });
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
            onSubmitEditing={send}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendBtn, { backgroundColor: accent }, !input.trim() && { opacity: 0.4 }]}
            onPress={send}
            disabled={!input.trim()}
          >
            <Text style={styles.sendText}>➤</Text>
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

function generateReply(
  text: string,
  opts: { wasAboutDay: boolean; context?: string },
): string[] {
  const t = text.toLowerCase();
  const mood = detectMood(t);
  const asksBack = asksAboutStella(t);

  // First message = the user's answer to "how was your day?"
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

  return [
    "I hear you — tell me a little more (colour, a specific piece, or the overall vibe) and I'll rework the outfit for you. ✨",
  ];
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  contextCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    padding: spacing(3),
    marginBottom: spacing(3),
  },
  contextLabel: {
    color: palette.textMuted,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  contextText: { color: palette.text, marginTop: 2 },
  bubbleRow: { marginBottom: spacing(3), maxWidth: "85%" },
  left: { alignSelf: "flex-start" },
  right: { alignSelf: "flex-end" },
  sender: { color: palette.textMuted, fontSize: 11, marginBottom: 2, marginLeft: spacing(1) },
  bubble: { paddingVertical: spacing(3), paddingHorizontal: spacing(4), borderRadius: radii.lg },
  aiBubble: { backgroundColor: palette.surface, borderTopLeftRadius: 4 },
  userBubble: { borderTopRightRadius: 4 },
  bubbleText: { color: palette.text, fontSize: 15, lineHeight: 21 },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing(2),
    padding: spacing(3),
    borderTopWidth: 1,
    borderTopColor: palette.surfaceAlt,
    backgroundColor: palette.background,
  },
  input: {
    flex: 1,
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    color: palette.text,
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(3),
    maxHeight: 120,
    fontSize: 15,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
  },
  sendText: { color: palette.background, fontSize: 18, fontWeight: "700" },
});
