import { Ionicons } from "@expo/vector-icons";
import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { refineApi } from "@/api/refine";
import { stylistApi } from "@/api/stylist";
import { tryonApi } from "@/api/tryon";
import type { Outfit, OutfitTryonSet } from "@/api/types";
import { ANGLE_LABEL } from "@/api/types";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export function OutfitDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "OutfitDetail">>();
  const nav = useNavigation<Nav>();
  const qc = useQueryClient();
  const { outfitId } = route.params;
  const scrollRef = useRef<ScrollView>(null);
  // KeyboardAvoidingView needs the nav header height as an offset, otherwise
  // `behavior="padding"` lifts content by the keyboard height but doesn't
  // account for the header sitting above — the composer ends up hidden
  // BEHIND the keyboard. iOS native-stack header on notched devices is
  // status-bar (~44) + nav-bar (~52) = ~96.
  const headerHeight = Platform.OS === "ios" ? 96 : 0;
  const [draft, setDraft] = useState("");

  const outfit = useQuery({
    queryKey: ["outfit", outfitId],
    queryFn: () => refineApi.getOutfit(outfitId),
    // Server enqueues the flat-lay composite as a background Arq job. While
    // it's outstanding we poll every 2.5s; once the key shows up (or the
    // user is past the stall threshold and has bailed) we stop.
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data || data.composite_image_key) return false;
      const ageMs = Date.now() - new Date(data.created_at).getTime();
      return ageMs < COMPOSITE_STALL_MS ? 2500 : false;
    },
  });

  const recompose = useMutation({
    mutationFn: () => refineApi.recompose(outfitId),
    onSuccess: (fresh) => {
      qc.setQueryData(["outfit", outfitId], fresh);
    },
    onError: (err) =>
      Alert.alert(
        "Couldn't regenerate flat-lay",
        err instanceof Error ? err.message : "Try again.",
      ),
  });

  const conversation = useQuery({
    queryKey: ["conversation", outfitId],
    queryFn: () => refineApi.getConversation(outfitId),
  });

  const tryon = useQuery({
    queryKey: ["tryonSet", outfitId],
    queryFn: async () => {
      try {
        return await tryonApi.getLatestTryonSet(outfitId);
      } catch (e) {
        const m = e instanceof Error ? e.message : "";
        if (/404|no tryon/i.test(m)) return null;
        throw e;
      }
    },
    // Poll while any render in the batch is still pending — they fan out
    // in parallel so we want to refresh as each one completes.
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return false;
      return data.renders.some((r) => r.status === "pending") ? 2500 : false;
    },
  });

  const refine = useMutation({
    mutationFn: (message: string) => refineApi.send(outfitId, message),
    onSuccess: (resp) => {
      // Optimistically update the outfit + conversation caches.
      qc.setQueryData(["outfit", outfitId], resp.outfit);
      qc.setQueryData<{ messages: typeof resp.message[] }>(
        ["conversation", outfitId],
        (prev) => ({
          messages: [
            ...(prev?.messages ?? []),
            ...[
              {
                id: `local-${Date.now()}`,
                role: "user" as const,
                content: draft,
                created_at: new Date().toISOString(),
              },
              resp.message,
            ],
          ],
        }),
      );
      // The previous tryon renders are stale once items change. Drop them so
      // the user sees the new outfit's CTA on next view.
      qc.setQueryData(["tryonSet", outfitId], null);
      setDraft("");
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    },
    onError: (err) =>
      Alert.alert(
        "Couldn't refine outfit",
        err instanceof Error ? err.message : "Try again.",
      ),
  });

  const requestTryon = useMutation({
    mutationFn: (opts?: { allAngles?: boolean }) =>
      tryonApi.requestTryon(outfitId, opts),
    onSuccess: () => tryon.refetch(),
    onError: (err) => {
      const m = err instanceof Error ? err.message : "";
      if (/412|base photo/i.test(m)) {
        Alert.alert(
          "Add a base photo first",
          "Open You → Add your base photo to enable try-on.",
          [
            { text: "Later", style: "cancel" },
            { text: "Add now", onPress: () => nav.navigate("BasePhoto") },
          ],
        );
        return;
      }
      Alert.alert("Try-on failed", m || "Try again later.");
    },
  });

  const record = useMutation({
    mutationFn: (kind: "worn" | "saved" | "skipped") =>
      stylistApi.recordEvent(outfitId, kind),
    onSuccess: () => nav.goBack(),
  });

  useEffect(() => {
    if (conversation.data?.messages?.length) {
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: false }), 50);
    }
  }, [conversation.data?.messages?.length]);

  const t = tryon.data;
  const o = outfit.data;
  const messages = conversation.data?.messages ?? [];

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={headerHeight}
    >
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: spacing(5), paddingBottom: spacing(8) }}
      >
        {/* Outfit composite or item strip */}
        {o && (
          <OutfitDisplay
            outfit={o}
            isRecomposing={recompose.isPending}
            onRecompose={() => recompose.mutate()}
          />
        )}

        {/* Try-on */}
        <View style={styles.tryonBox}>
          <TryonSetView
            data={t}
            isRequesting={requestTryon.isPending}
            onRequest={() => requestTryon.mutate(undefined)}
            onRequestAllAngles={() =>
              requestTryon.mutate({ allAngles: true })
            }
          />
        </View>

        {/* Chat */}
        <Text style={styles.section}>Chat with your stylist</Text>
        {messages.length === 0 ? (
          <View style={styles.chatEmpty}>
            <Text style={styles.chatHint}>
              Tap a suggestion or type your own at the bottom.
            </Text>
            <View style={styles.suggestionRow}>
              {CHAT_SUGGESTIONS.map((s) => (
                <Pressable
                  key={s}
                  style={styles.suggestionChip}
                  onPress={() => {
                    setDraft(s);
                    // Send immediately — most users want a one-tap path.
                    refine.mutate(s);
                  }}
                  disabled={refine.isPending}
                >
                  <Text style={styles.suggestionText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : (
          <View style={styles.thread}>
            {messages.map((m) => (
              <View
                key={m.id}
                style={[
                  styles.bubble,
                  m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant,
                ]}
              >
                <Text style={m.role === "user" ? styles.bubbleUserText : styles.bubbleAsstText}>
                  {m.content}
                </Text>
              </View>
            ))}
            {refine.isPending && (
              <View style={[styles.bubble, styles.bubbleAssistant]}>
                <ActivityIndicator color={palette.textMuted} />
              </View>
            )}
          </View>
        )}

        <Text style={styles.section}>How&apos;d you feel about this outfit?</Text>
        <Pressable
          style={[styles.button, styles.primary]}
          onPress={() => record.mutate("worn")}
        >
          <Ionicons name="checkmark-circle-outline" size={18} color={palette.onAccent} />
          <Text style={styles.primaryText}>Wore it today</Text>
        </Pressable>
        <Pressable style={styles.button} onPress={() => record.mutate("saved")}>
          <Ionicons name="bookmark-outline" size={18} color={palette.text} />
          <Text style={styles.buttonText}>Save for later</Text>
        </Pressable>
        <Pressable style={styles.button} onPress={() => record.mutate("skipped")}>
          <Ionicons name="close-circle-outline" size={18} color={palette.text} />
          <Text style={styles.buttonText}>Not for me</Text>
        </Pressable>
      </ScrollView>

      {/* Chat input pinned to the bottom */}
      <View style={styles.composer}>
        <TextInput
          style={styles.composerInput}
          value={draft}
          onChangeText={setDraft}
          placeholder="Ask the stylist to change something…"
          placeholderTextColor={palette.textMuted}
          editable={!refine.isPending}
          multiline
          maxLength={500}
        />
        <Pressable
          style={[
            styles.sendButton,
            (!draft.trim() || refine.isPending) && styles.sendButtonDisabled,
          ]}
          disabled={!draft.trim() || refine.isPending}
          onPress={() => {
            Keyboard.dismiss();
            refine.mutate(draft.trim());
          }}
        >
          <Text style={styles.sendButtonText}>Send</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

// IDM-VTON renders one garment at ~25s, chained for multi-garment outfits.
// A typical 3-garment outfit (top + bottom + outerwear) clocks ~75-100s per
// angle. We surface "taking longer than usual" at 150s so a stuck render
// surfaces fast but normal renders aren't flagged as slow.
const TRYON_STALL_MS = 150_000;

// One-tap chat suggestions. Tapping fires the refine call immediately —
// users shouldn't have to type their first message to learn what's possible.
const CHAT_SUGGESTIONS: string[] = [
  "Make it dressier",
  "More casual",
  "Swap the top",
  "Different shoes",
  "Go more minimal",
];
// Auto-advance interval for the multi-angle carousel. 2.5s per frame is fast
// enough to feel like a continuous look-at-yourself motion, slow enough to
// actually see the outfit at each angle.
const CAROUSEL_INTERVAL_MS = 2500;

function TryonSetView({
  data,
  isRequesting,
  onRequest,
  onRequestAllAngles,
}: {
  data: OutfitTryonSet | null | undefined;
  isRequesting: boolean;
  onRequest: () => void;
  onRequestAllAngles: () => void;
}) {
  const renders = data?.renders ?? [];
  const ready = renders.filter((r) => r.status === "ready" && r.rendered_image_key);
  const anyPending = renders.some((r) => r.status === "pending");
  const allFailed =
    renders.length > 0 && renders.every((r) => r.status === "failed");

  // Auto-advance through ready renders. Resets to 0 when the set changes,
  // pauses automatically while new renders are streaming in.
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(0);
  }, [data?.renders?.length, data?.renders?.[0]?.id]);
  useEffect(() => {
    if (ready.length < 2) return;
    const timer = setInterval(() => {
      setIdx((i) => (i + 1) % ready.length);
    }, CAROUSEL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [ready.length]);

  // No try-on yet → CTA.
  if (!data || renders.length === 0) {
    return (
      <View style={styles.tryonPlaceholder}>
        <Text style={styles.tryonPlaceholderText}>
          See yourself wearing this outfit
        </Text>
        <Text style={styles.tryonSubText}>
          We render you in the FULL outfit — top + bottom + outerwear —
          one garment at a time. Takes ~75-100 seconds. The wait is the
          price of identity preservation (it&apos;s actually you, not an
          AI-generated stranger). Render all 4 angles after the first
          one finishes if you want the carousel.
        </Text>
        <Pressable
          style={[styles.button, styles.primary]}
          onPress={onRequest}
          disabled={isRequesting}
        >
          {isRequesting ? (
            <ActivityIndicator color={palette.onAccent} />
          ) : (
            <>
              <Ionicons name="sparkles-outline" size={18} color={palette.onAccent} />
              <Text style={styles.primaryText}>Try on me</Text>
            </>
          )}
        </Pressable>
      </View>
    );
  }

  if (allFailed) {
    const firstFail = renders[0];
    return (
      <View style={styles.tryonPlaceholder}>
        <Text style={styles.errorText}>
          Couldn&apos;t render this look: {firstFail?.error_message ?? "unknown error"}
        </Text>
        <Pressable
          style={[styles.button, styles.primary]}
          onPress={onRequest}
          disabled={isRequesting}
        >
          <Text style={styles.primaryText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  // At least one render is ready — show the carousel. Stragglers (pending)
  // are surfaced as a small status hint at the bottom.
  if (ready.length > 0) {
    const current = ready[idx] ?? ready[0];
    if (!current) return null;
    return (
      <View>
        <Image
          source={{
            uri: `${baseUrl}/api/v1/wardrobe/_local_read/${current.rendered_image_key}?v=${current.id}`,
          }}
          style={styles.tryonImage}
          contentFit="cover"
        />
        {ready.length > 1 && (
          <View style={styles.carouselDots}>
            {ready.map((r, i) => (
              <Pressable
                key={r.id}
                onPress={() => setIdx(i)}
                style={[styles.dot, i === idx && styles.dotActive]}
              />
            ))}
          </View>
        )}
        <View style={styles.carouselLabel}>
          <Text style={styles.carouselLabelText}>
            {current.angle ? ANGLE_LABEL[current.angle] : "View"}
            {ready.length > 1 ? `  ·  ${idx + 1} of ${ready.length}` : ""}
          </Text>
          {anyPending && (
            <Text style={styles.carouselPending}>
              Rendering more angles…
            </Text>
          )}
        </View>
        <View style={styles.regenRow}>
          <Pressable
            style={styles.regenButton}
            onPress={onRequest}
            disabled={isRequesting}
          >
            <Text style={styles.regenText}>↻  Render again</Text>
          </Pressable>
          {ready.length === 1 && (
            <Pressable
              style={styles.regenButton}
              onPress={onRequestAllAngles}
              disabled={isRequesting}
            >
              <Text style={styles.regenText}>Render all 4 angles</Text>
            </Pressable>
          )}
        </View>
      </View>
    );
  }

  // All renders still pending — show the first one's stall UI as the canonical state.
  const first = renders[0];
  if (!first) return null;
  return (
    <PendingTryon
      createdAt={first.created_at}
      isRetrying={isRequesting}
      onRetry={onRequest}
    />
  );
}

// Pillow flat-lay composition is ~100-500ms once the worker picks the job up.
// After 25s with no composite_image_key we treat the Arq job as dead and offer
// a manual recompose. Until then we show a "Generating outfit image…" state
// instead of silently falling back to the thumbnail strip.
const COMPOSITE_STALL_MS = 25_000;

function PendingTryon({
  createdAt,
  isRetrying,
  onRetry,
}: {
  createdAt: string;
  isRetrying: boolean;
  onRetry: () => void;
}) {
  const createdMs = useMemo(() => new Date(createdAt).getTime(), [createdAt]);
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    const elapsed = Date.now() - createdMs;
    if (elapsed >= TRYON_STALL_MS) {
      setStalled(true);
      return;
    }
    const timer = setTimeout(() => setStalled(true), TRYON_STALL_MS - elapsed);
    return () => clearTimeout(timer);
  }, [createdMs]);

  if (stalled) {
    return (
      <View style={styles.tryonPlaceholder}>
        <Ionicons name="time-outline" size={28} color={palette.textMuted} />
        <Text style={styles.tryonPlaceholderText}>
          Render is taking longer than usual.
        </Text>
        <Text style={styles.tryonSubText}>
          The model is still working. Tap Render again to retry from
          scratch, or wait a bit longer — full outfits can stretch
          past 90 seconds when Replicate is busy.
        </Text>
        <Pressable
          style={[styles.button, styles.primary]}
          onPress={onRetry}
          disabled={isRetrying}
        >
          {isRetrying ? (
            <ActivityIndicator color={palette.onAccent} />
          ) : (
            <Text style={styles.primaryText}>Render again</Text>
          )}
        </Pressable>
      </View>
    );
  }
  return (
    <View style={styles.tryonPlaceholder}>
      <ActivityIndicator color={palette.accent} size="large" />
      <Text style={styles.tryonPlaceholderText}>
        Rendering you in this look…
      </Text>
      <Text style={styles.tryonSubText}>
        ~75-100 seconds for the full outfit. The AI is dressing your actual
        photo one garment at a time — face, body, and pose stay yours.
      </Text>
    </View>
  );
}

function OutfitDisplay({
  outfit,
  isRecomposing,
  onRecompose,
}: {
  outfit: Outfit;
  isRecomposing: boolean;
  onRecompose: () => void;
}) {
  const createdMs = useMemo(
    () => new Date(outfit.created_at).getTime(),
    [outfit.created_at],
  );
  const [stalled, setStalled] = useState(
    () => Date.now() - createdMs >= COMPOSITE_STALL_MS,
  );
  useEffect(() => {
    if (outfit.composite_image_key) return;
    if (stalled) return;
    const elapsed = Date.now() - createdMs;
    if (elapsed >= COMPOSITE_STALL_MS) {
      setStalled(true);
      return;
    }
    const timer = setTimeout(
      () => setStalled(true),
      COMPOSITE_STALL_MS - elapsed,
    );
    return () => clearTimeout(timer);
  }, [createdMs, outfit.composite_image_key, stalled]);

  // Happy path — composite is ready.
  if (outfit.composite_image_key) {
    return (
      <Image
        source={{
          uri: `${baseUrl}/api/v1/wardrobe/_local_read/${outfit.composite_image_key}?v=${outfit.id}`,
        }}
        style={styles.composite}
        contentFit="cover"
      />
    );
  }

  const thumbStrip = (
    <View style={styles.itemStrip}>
      {outfit.items.map((oi) => (
        <View key={oi.item.id} style={styles.itemCell}>
          {oi.item.thumbnail_key ? (
            <Image
              source={{
                uri: `${baseUrl}/api/v1/wardrobe/_local_read/${oi.item.thumbnail_key}?v=${oi.item.created_at}`,
              }}
              style={styles.itemThumb}
              contentFit="cover"
            />
          ) : (
            <View style={[styles.itemThumb, { backgroundColor: palette.surfaceAlt }]} />
          )}
          <Text style={styles.itemSlot}>{oi.slot}</Text>
        </View>
      ))}
    </View>
  );

  // Still cooking — the worker is normally <1s but Redis/queue depth can
  // push it out. Show a clear "we're working on it" while polling.
  if (!stalled) {
    return (
      <View style={styles.compositePending}>
        <ActivityIndicator color={palette.accent} size="large" />
        <Text style={styles.compositePendingText}>Generating outfit image…</Text>
        {thumbStrip}
      </View>
    );
  }

  // Stalled — composer didn't finish in time. Surface the thumbnail strip
  // (so the user can still see the look) plus a manual "Generate again"
  // CTA that re-enqueues the Arq job.
  return (
    <View>
      {thumbStrip}
      <View style={styles.compositeStalled}>
        <Ionicons name="image-outline" size={22} color={palette.textMuted} />
        <Text style={styles.compositeStalledText}>
          Couldn&apos;t generate the flat-lay image.
        </Text>
        <Pressable
          style={[styles.button, styles.primary, styles.compositeRetry]}
          onPress={onRecompose}
          disabled={isRecomposing}
        >
          {isRecomposing ? (
            <ActivityIndicator color={palette.onAccent} />
          ) : (
            <>
              <Ionicons
                name="refresh-outline"
                size={16}
                color={palette.onAccent}
              />
              <Text style={styles.primaryText}>Generate again</Text>
            </>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  composite: {
    width: "100%",
    aspectRatio: 1,
    borderRadius: radii.lg,
    backgroundColor: palette.surfaceAlt,
    marginBottom: spacing(5),
  },
  itemStrip: {
    flexDirection: "row",
    gap: spacing(2),
    marginBottom: spacing(5),
  },
  compositePending: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: spacing(5),
    alignItems: "center",
    gap: spacing(3),
    marginBottom: spacing(5),
  },
  compositePendingText: {
    color: palette.text,
    fontSize: 14,
    fontWeight: "500",
  },
  compositeStalled: {
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    padding: spacing(4),
    alignItems: "center",
    gap: spacing(3),
    marginBottom: spacing(5),
  },
  compositeStalledText: {
    color: palette.textMuted,
    fontSize: 13,
    textAlign: "center",
  },
  compositeRetry: {
    marginBottom: 0,
    marginTop: spacing(1),
    paddingHorizontal: spacing(5),
  },
  itemCell: { flex: 1, alignItems: "center" },
  itemThumb: {
    width: "100%",
    aspectRatio: 1,
    borderRadius: radii.md,
    backgroundColor: palette.surfaceAlt,
  },
  itemSlot: {
    color: palette.textMuted,
    fontSize: 11,
    marginTop: 4,
    textTransform: "capitalize",
  },
  tryonBox: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    overflow: "hidden",
    marginBottom: spacing(6),
  },
  tryonPlaceholder: { padding: spacing(8), alignItems: "center", gap: spacing(4) },
  tryonPlaceholderText: {
    color: palette.text,
    fontSize: 16,
    fontWeight: "500",
    textAlign: "center",
  },
  tryonSubText: {
    color: palette.textMuted,
    fontSize: 12,
    lineHeight: 17,
    textAlign: "center",
    paddingHorizontal: spacing(2),
  },
  tryonImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: palette.surfaceAlt,
  },
  regenButton: { padding: spacing(3), alignItems: "center", flex: 1 },
  regenText: { color: palette.textMuted, fontWeight: "600", fontSize: 13 },
  regenRow: {
    flexDirection: "row",
    gap: spacing(1),
    paddingHorizontal: spacing(2),
  },
  carouselDots: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing(2),
    paddingTop: spacing(3),
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: palette.surfaceAlt,
  },
  dotActive: { backgroundColor: palette.accent },
  carouselLabel: {
    paddingHorizontal: spacing(4),
    paddingTop: spacing(2),
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  carouselLabelText: { color: palette.text, fontWeight: "600", fontSize: 14 },
  carouselPending: { color: palette.textMuted, fontSize: 12, fontStyle: "italic" },
  section: {
    color: palette.text,
    fontSize: 18,
    fontWeight: "700",
    marginTop: spacing(2),
    marginBottom: spacing(3),
  },
  chatEmpty: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    marginBottom: spacing(6),
    gap: spacing(3),
  },
  chatHint: { color: palette.textMuted, lineHeight: 20 },
  suggestionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing(2),
  },
  suggestionChip: {
    backgroundColor: palette.background,
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(2),
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
  },
  suggestionText: {
    color: palette.text,
    fontSize: 13,
    fontWeight: "500",
  },
  thread: { gap: spacing(3), marginBottom: spacing(6) },
  bubble: {
    padding: spacing(3),
    borderRadius: radii.md,
    maxWidth: "85%",
  },
  bubbleUser: {
    backgroundColor: palette.accent,
    alignSelf: "flex-end",
    borderBottomRightRadius: 4,
  },
  bubbleUserText: { color: palette.onAccent, lineHeight: 20 },
  bubbleAssistant: {
    backgroundColor: palette.surface,
    alignSelf: "flex-start",
    borderBottomLeftRadius: 4,
  },
  bubbleAsstText: { color: palette.text, lineHeight: 20 },
  button: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing(2),
    marginBottom: spacing(3),
  },
  buttonText: { color: palette.text, fontWeight: "600", fontSize: 16 },
  primary: { backgroundColor: palette.accent },
  primaryText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
  errorText: { color: palette.danger, textAlign: "center" },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: spacing(3),
    borderTopWidth: 1,
    borderTopColor: palette.surfaceAlt,
    backgroundColor: palette.surface,
    gap: spacing(2),
  },
  composerInput: {
    flex: 1,
    color: palette.text,
    backgroundColor: palette.background,
    borderRadius: radii.md,
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(3),
    maxHeight: 120,
    fontSize: 15,
  },
  sendButton: {
    backgroundColor: palette.accent,
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(3),
    borderRadius: radii.md,
  },
  sendButtonDisabled: { opacity: 0.4 },
  sendButtonText: { color: palette.onAccent, fontWeight: "700" },
});
