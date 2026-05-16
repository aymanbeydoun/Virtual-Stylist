import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { wardrobeApi } from "@/api/wardrobe";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

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
            <Pressable
              style={styles.card}
              onPress={() => nav.navigate("ItemDetail", { itemId: item.id })}
            >
              {item.thumbnail_key ? (
                <Image
                  source={{ uri: `${baseUrl}/api/v1/wardrobe/_local_read/${item.thumbnail_key}` }}
                  style={styles.thumb}
                  contentFit="cover"
                />
              ) : (
                <View style={[styles.thumb, styles.thumbPlaceholder]}>
                  <Text style={{ color: palette.textMuted }}>
                    {item.status === "pending" ? "Tagging…" : "?"}
                  </Text>
                </View>
              )}
              <Text style={styles.cardCategory} numberOfLines={1}>
                {item.category ?? "Untagged"}
              </Text>
              {item.needs_review && <Text style={styles.review}>Tap to review</Text>}
            </Pressable>
          )}
        />
      )}
    </SafeAreaView>
  );
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
  addButtonText: { color: palette.background, fontWeight: "700" },
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
  thumbPlaceholder: { alignItems: "center", justifyContent: "center" },
  cardCategory: { color: palette.text, padding: spacing(3), fontSize: 13 },
  review: { color: palette.accent, paddingHorizontal: spacing(3), paddingBottom: spacing(3) },
});
