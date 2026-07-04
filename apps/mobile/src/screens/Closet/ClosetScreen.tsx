import { FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DEMO_CLOSET, type DemoItem } from "@/data/demoCloset";
import { useActiveProfile } from "@/state/profile";
import { useAccent } from "@/state/theme";
import { palette, radii, spacing } from "@/theme";

const SLOT_LABELS: Record<DemoItem["slot"], string> = {
  top: "Top",
  bottom: "Bottom",
  dress: "Dress",
  outerwear: "Outerwear",
  shoes: "Shoes",
  accessory: "Accessory",
};

export function ClosetScreen() {
  const profile = useActiveProfile();
  const accent = useAccent().color;

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>Closet</Text>
          <Text style={styles.title}>{profile.ownerLabel}</Text>
        </View>
        <View style={[styles.pill, { borderColor: accent }]}>
          <Text style={[styles.pillText, { color: accent }]}>Demo closet</Text>
        </View>
      </View>

      <Text style={styles.subtitle}>
        Here&apos;s an example wardrobe to try things out. Head to ✨ Style and tap
        Staile me!
      </Text>

      <FlatList
        data={DEMO_CLOSET}
        keyExtractor={(i) => i.id}
        numColumns={2}
        contentContainerStyle={{ padding: spacing(3) }}
        columnWrapperStyle={{ gap: spacing(3) }}
        ItemSeparatorComponent={() => <View style={{ height: spacing(3) }} />}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={[styles.thumb, { backgroundColor: item.color }]}>
              <Text style={styles.thumbEmoji}>{item.emoji}</Text>
            </View>
            <Text style={styles.cardName} numberOfLines={1}>
              {item.name}
            </Text>
            <Text style={styles.cardSlot}>{SLOT_LABELS[item.slot]}</Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing(5),
    paddingTop: spacing(5),
  },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  pill: {
    backgroundColor: palette.surface,
    borderColor: palette.accent,
    borderWidth: 1,
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(1.5),
    borderRadius: radii.pill,
  },
  pillText: { color: palette.accent, fontWeight: "700", fontSize: 12 },
  subtitle: {
    color: palette.textMuted,
    paddingHorizontal: spacing(5),
    paddingTop: spacing(3),
    paddingBottom: spacing(2),
    fontSize: 13,
    lineHeight: 18,
  },
  card: { flex: 1, backgroundColor: palette.surface, borderRadius: radii.md, overflow: "hidden" },
  thumb: { width: "100%", aspectRatio: 1, alignItems: "center", justifyContent: "center" },
  thumbEmoji: { fontSize: 52 },
  cardName: { color: palette.text, paddingHorizontal: spacing(3), paddingTop: spacing(3), fontSize: 14, fontWeight: "600" },
  cardSlot: {
    color: palette.textMuted,
    paddingHorizontal: spacing(3),
    paddingBottom: spacing(3),
    paddingTop: 2,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
});
