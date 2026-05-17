import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { wardrobeApi } from "@/api/wardrobe";
import type { WardrobeItem } from "@/api/types";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

// How long we let an item sit at status='pending' before treating it as stalled
// and showing a recovery affordance. The backend's stalled-sweeper kicks in at
// 10 minutes; we show the UI nudge much sooner.
const PENDING_STALL_MS = 90_000;

export function ClosetScreen() {
  const nav = useNavigation<Nav>();
  const profile = useActiveProfile();
  const items = useQuery({
    queryKey: ["wardrobe", profile.ownerKind, profile.ownerId],
    queryFn: () =>
      wardrobeApi.listItems({
        kind: profile.ownerKind,
        id: profile.ownerId ?? undefined,
      }),
    // Auto-refresh while anything is still tagging.
    refetchInterval: (q) => {
      const data = q.state.data ?? [];
      return data.some((i) => i.status === "pending") ? 4000 : false;
    },
  });

  const readyCount = (items.data ?? []).filter((i) => i.status === "ready").length;
  const showGapsPromo = readyCount >= 4;

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.eyebrow}>Closet · {readyCount} items</Text>
          <Text style={styles.title}>{profile.ownerLabel}</Text>
        </View>
        <View style={styles.headerActions}>
          <Pressable style={styles.ghostButton} onPress={() => nav.navigate("Gaps")}>
            <Text style={styles.ghostButtonText}>Gaps</Text>
          </Pressable>
          <Pressable style={styles.addButton} onPress={() => nav.navigate("AddItem")}>
            <Text style={styles.addButtonText}>+ Add</Text>
          </Pressable>
        </View>
      </View>

      {showGapsPromo && (
        <Pressable style={styles.promo} onPress={() => nav.navigate("Gaps")}>
          <View style={styles.promoDot} />
          <View style={{ flex: 1 }}>
            <Text style={styles.promoTitle}>See what your closet is missing</Text>
            <Text style={styles.promoBody}>
              AI looks at your wardrobe holistically and finds outfits you can&apos;t yet build.
            </Text>
          </View>
          <Text style={styles.promoArrow}>›</Text>
        </Pressable>
      )}

      {items.isLoading ? (
        <Text style={styles.empty}>Loading…</Text>
      ) : items.data && items.data.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>Your closet is empty</Text>
          <Text style={styles.emptyText}>
            Snap or import a few items. We&apos;ll tag them for you.
          </Text>
        </View>
      ) : (
        <FlatList
          data={items.data ?? []}
          keyExtractor={(i) => i.id}
          numColumns={2}
          contentContainerStyle={{ padding: spacing(3) }}
          columnWrapperStyle={{ gap: spacing(3) }}
          ItemSeparatorComponent={() => <View style={{ height: spacing(3) }} />}
          renderItem={({ item }) => (
            <ItemCard
              item={item}
              onOpen={() => nav.navigate("ItemDetail", { itemId: item.id })}
            />
          )}
        />
      )}
    </SafeAreaView>
  );
}

function ItemCard({ item, onOpen }: { item: WardrobeItem; onOpen: () => void }) {
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["wardrobe", profile.ownerKind, profile.ownerId] });

  // Track wall-time since the item entered pending so we can show "still tagging"
  // → "this is taking a while" without blocking forever.
  const createdMs = useMemo(() => new Date(item.created_at).getTime(), [item.created_at]);
  const [stalled, setStalled] = useStalled(item.status === "pending", createdMs);

  const retry = useMutation({
    mutationFn: () => wardrobeApi.retry(item.id),
    onSuccess: () => {
      setStalled(false);
      invalidate();
    },
    onError: (err) =>
      Alert.alert("Couldn't retry", err instanceof Error ? err.message : "Try again."),
  });
  const remove = useMutation({
    mutationFn: () => wardrobeApi.remove(item.id),
    onSuccess: invalidate,
    onError: (err) =>
      Alert.alert("Couldn't delete", err instanceof Error ? err.message : "Try again."),
  });

  const promptActions = (kind: "failed" | "stalled") => {
    const reason = item.failure_reason;
    Alert.alert(
      kind === "failed" ? "Couldn't tag this photo" : "Still tagging…",
      kind === "failed"
        ? reason ?? "The AI couldn't analyse this image. Retry, or delete and upload a different photo."
        : "This is taking longer than usual. Retry now, or wait a bit longer.",
      [
        { text: "Cancel", style: "cancel" },
        { text: "Retry", onPress: () => retry.mutate() },
        ...(kind === "failed"
          ? [{ text: "Delete", style: "destructive" as const, onPress: () => remove.mutate() }]
          : []),
      ],
    );
  };

  const tappable = item.status !== "pending" || stalled;

  return (
    <Pressable
      style={styles.card}
      onPress={() => {
        if (item.status === "failed") return promptActions("failed");
        if (item.status === "pending" && stalled) return promptActions("stalled");
        if (tappable) onOpen();
      }}
    >
      {item.status === "ready" && item.thumbnail_key ? (
        <Image
          source={{
            uri: `${baseUrl}/api/v1/wardrobe/_local_read/${item.thumbnail_key}?v=${encodeURIComponent(
              item.created_at,
            )}`,
          }}
          style={styles.thumb}
          contentFit="cover"
        />
      ) : item.status === "pending" ? (
        <View style={[styles.thumb, styles.thumbPlaceholder]}>
          {retry.isPending ? (
            <ActivityIndicator color={palette.accent} />
          ) : stalled ? (
            <>
              <Ionicons name="time-outline" size={24} color={palette.textMuted} />
              <Text style={styles.thumbLabel}>Taking a while</Text>
              <Text style={styles.thumbSubLabel}>Tap to retry</Text>
            </>
          ) : (
            <>
              <ActivityIndicator color={palette.accent} />
              <Text style={styles.thumbLabel}>Tagging…</Text>
            </>
          )}
        </View>
      ) : (
        // status === "failed"
        <View style={[styles.thumb, styles.thumbPlaceholder, styles.thumbFailed]}>
          <Ionicons name="alert-circle-outline" size={28} color={palette.danger} />
          <Text style={[styles.thumbLabel, { color: palette.danger }]}>Couldn&apos;t tag</Text>
          <Text style={styles.thumbSubLabel}>Tap for options</Text>
        </View>
      )}
      <View style={styles.cardFooter}>
        <Text style={styles.cardCategory} numberOfLines={1}>
          {item.category ?? (item.status === "failed" ? "Failed" : "Untagged")}
        </Text>
        {item.needs_review && item.status === "ready" && (
          <View style={styles.reviewBadge}>
            <Ionicons name="warning-outline" size={11} color={palette.accentDark} />
            <Text style={styles.reviewBadgeText}>Review</Text>
          </View>
        )}
      </View>
    </Pressable>
  );
}

/**
 * Returns [stalled, setStalled]. `stalled` flips to true PENDING_STALL_MS after
 * the item entered pending state. Resets when status changes.
 */
function useStalled(isPending: boolean, createdMs: number) {
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    if (!isPending) {
      setStalled(false);
      return;
    }
    const elapsed = Date.now() - createdMs;
    if (elapsed >= PENDING_STALL_MS) {
      setStalled(true);
      return;
    }
    const timer = setTimeout(() => setStalled(true), PENDING_STALL_MS - elapsed);
    return () => clearTimeout(timer);
  }, [isPending, createdMs]);
  return [stalled, setStalled] as const;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing(5),
  },
  headerActions: { flexDirection: "row", gap: spacing(2), alignItems: "center" },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  addButton: {
    backgroundColor: palette.accent,
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(2),
    borderRadius: radii.pill,
  },
  addButtonText: { color: palette.onAccent, fontWeight: "700" },
  ghostButton: {
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(2),
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
  },
  ghostButtonText: { color: palette.text, fontWeight: "600" },
  promo: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: spacing(4),
    marginBottom: spacing(3),
    padding: spacing(4),
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    gap: spacing(3),
  },
  promoDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: palette.accent,
  },
  promoTitle: { color: palette.text, fontWeight: "600", marginBottom: 2 },
  promoBody: { color: palette.textMuted, fontSize: 13, lineHeight: 18 },
  promoArrow: { color: palette.textMuted, fontSize: 24, fontWeight: "300" },
  empty: { color: palette.textMuted, padding: spacing(6) },
  emptyState: { padding: spacing(8), alignItems: "center" },
  emptyTitle: { color: palette.text, fontSize: 18, fontWeight: "600", marginBottom: spacing(2) },
  emptyText: { color: palette.textMuted, textAlign: "center" },
  card: { flex: 1, backgroundColor: palette.surface, borderRadius: radii.md, overflow: "hidden" },
  thumb: { width: "100%", aspectRatio: 1, backgroundColor: palette.surfaceAlt },
  thumbPlaceholder: { alignItems: "center", justifyContent: "center", gap: 4 },
  thumbFailed: { backgroundColor: "#FBEAEA" },
  thumbLabel: { color: palette.textMuted, fontSize: 12, fontWeight: "600" },
  thumbSubLabel: { color: palette.textMuted, fontSize: 11 },
  cardFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing(3),
    gap: spacing(2),
  },
  cardCategory: { color: palette.text, fontSize: 13, flex: 1 },
  reviewBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.sm,
    backgroundColor: palette.background,
  },
  reviewBadgeText: { color: palette.accentDark, fontSize: 10, fontWeight: "700", letterSpacing: 0.5 },
});
