import { Ionicons } from "@expo/vector-icons";
import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
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
import type { Outfit } from "@/api/types";
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
  const [draft, setDraft] = useState("");

  const outfit = useQuery({
    queryKey: ["outfit", outfitId],
    queryFn: () => refineApi.getOutfit(outfitId),
  });

  const conversation = useQuery({
    queryKey: ["conversation", outfitId],
    queryFn: () => refineApi.getConversation(outfitId),
  });

  const tryon = useQuery({
    queryKey: ["tryon", outfitId],
    queryFn: async () => {
      try {
        return await tryonApi.getLatestTryon(outfitId);
      } catch (e) {
        const m = e instanceof Error ? e.message : "";
        if (/404|no tryon/i.test(m)) return null;
        throw e;
      }
    },
    refetchInterval: (q) => {
      const data = q.state.data;
      return data && data.status === "pending" ? 2500 : false;
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
      // The previous tryon render is stale once items change. Drop it so the
      // user sees the new outfit's CTA on next view.
      qc.setQueryData(["tryon", outfitId], null);
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
    mutationFn: () => tryonApi.requestTryon(outfitId),
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
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: spacing(5), paddingBottom: spacing(8) }}
      >
        {/* Outfit composite or item strip */}
        {o && <OutfitDisplay outfit={o} />}

        {/* Try-on */}
        <View style={styles.tryonBox}>
          {!t && (
            <View style={styles.tryonPlaceholder}>
              <Text style={styles.tryonPlaceholderText}>
                See yourself wearing this outfit
              </Text>
              <Pressable
                style={[styles.button, styles.primary]}
                onPress={() => requestTryon.mutate()}
                disabled={requestTryon.isPending}
              >
                {requestTryon.isPending ? (
                  <ActivityIndicator color={palette.onAccent} />
                ) : (
                  <>
                    <Ionicons name="sparkles-outline" size={18} color={palette.onAccent} />
                    <Text style={styles.primaryText}>Try on me</Text>
                  </>
                )}
              </Pressable>
            </View>
          )}
          {t?.status === "pending" && (
            <View style={styles.tryonPlaceholder}>
              <ActivityIndicator color={palette.accent} size="large" />
              <Text style={styles.tryonPlaceholderText}>
                Rendering you in this look… 10-15s
              </Text>
            </View>
          )}
          {t?.status === "ready" && t.rendered_image_key && (
            <View>
              <Image
                source={{
                  uri: `${baseUrl}/api/v1/wardrobe/_local_read/${t.rendered_image_key}?v=${t.id}`,
                }}
                style={styles.tryonImage}
                contentFit="cover"
              />
              <Pressable
                style={styles.regenButton}
                onPress={() => requestTryon.mutate()}
                disabled={requestTryon.isPending}
              >
                <Text style={styles.regenText}>↻  Render again</Text>
              </Pressable>
            </View>
          )}
          {t?.status === "failed" && (
            <View style={styles.tryonPlaceholder}>
              <Text style={styles.errorText}>
                Couldn&apos;t render this look: {t.error_message ?? "unknown error"}
              </Text>
              <Pressable
                style={[styles.button, styles.primary]}
                onPress={() => requestTryon.mutate()}
                disabled={requestTryon.isPending}
              >
                <Text style={styles.primaryText}>Try again</Text>
              </Pressable>
            </View>
          )}
        </View>

        {/* Chat */}
        <Text style={styles.section}>Chat with your stylist</Text>
        {messages.length === 0 ? (
          <View style={styles.chatEmpty}>
            <Text style={styles.chatHint}>
              Ask anything: &quot;swap the bomber for something dressier&quot;,
              &quot;edgier shoes please&quot;, &quot;keep it but go more minimal&quot;.
            </Text>
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
          onPress={() => refine.mutate(draft.trim())}
        >
          <Text style={styles.sendButtonText}>Send</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function OutfitDisplay({ outfit }: { outfit: Outfit }) {
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
  return (
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
  tryonImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: palette.surfaceAlt,
  },
  regenButton: { padding: spacing(3), alignItems: "center" },
  regenText: { color: palette.textMuted, fontWeight: "600" },
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
  },
  chatHint: { color: palette.textMuted, lineHeight: 20, fontStyle: "italic" },
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
