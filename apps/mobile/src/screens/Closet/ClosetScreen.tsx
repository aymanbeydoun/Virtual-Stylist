import { LinearGradient } from "expo-linear-gradient";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GarmentIcon } from "@/components/GarmentIcon";
import { DEMO_CLOSET, type DemoItem } from "@/data/demoCloset";
import { useActiveProfile } from "@/state/profile";
import { useAccent } from "@/state/theme";
import { fonts, glass, palette, radii, spacing } from "@/theme";

const SLOT_LABELS: Record<DemoItem["slot"], string> = {
  top: "Top",
  bottom: "Bottom",
  dress: "Dress",
  outerwear: "Outerwear",
  shoes: "Shoes",
  accessory: "Accessory",
};

/** Muted neutral backdrop behind every garment — focus stays on the piece. */
const CARD_BACKDROP = ["#15171E", "#0D0F14"] as const;

export function ClosetScreen() {
  const profile = useActiveProfile();
  const accent = useAccent().color;

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>CLOSET</Text>
          <Text style={styles.title}>{profile.ownerLabel}</Text>
        </View>
        <View style={[styles.pill, { borderColor: accent }]}>
          <Text style={[styles.pillText, { color: accent }]}>DEMO CLOSET</Text>
        </View>
      </View>

      <Text style={styles.subtitle}>
        Here&apos;s an example wardrobe to try things out. Head to Style and tap
        STaiLE ME!
      </Text>

      <FlatList
        data={DEMO_CLOSET}
        keyExtractor={(i) => i.id}
        numColumns={2}
        contentContainerStyle={{ padding: spacing(3), paddingBottom: spacing(8) }}
        columnWrapperStyle={{ gap: spacing(3) }}
        ItemSeparatorComponent={() => <View style={{ height: spacing(3) }} />}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <LinearGradient colors={CARD_BACKDROP} style={styles.garmentWell}>
              <GarmentIcon kind={item.icon} color={item.color} size={92} />
            </LinearGradient>
            <View style={styles.cardMeta}>
              <Text style={styles.cardName} numberOfLines={1}>
                {item.name}
              </Text>
              <Text style={styles.cardSlot}>{SLOT_LABELS[item.slot]}</Text>
            </View>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing(5),
    paddingTop: spacing(5),
  },
  eyebrow: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 2.5,
  },
  title: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 28,
    marginTop: 4,
    letterSpacing: 0.5,
  },
  pill: {
    backgroundColor: palette.surface,
    borderWidth: 1,
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(1.5),
    borderRadius: radii.pill,
  },
  pillText: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.5 },
  subtitle: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    paddingHorizontal: spacing(5),
    paddingTop: spacing(3),
    paddingBottom: spacing(2),
    fontSize: 13,
    lineHeight: 19,
  },
  // Tall portrait cards — premium e-commerce grid geometry. maxWidth keeps a
  // lone card in the final row from stretching to double size.
  card: {
    ...glass,
    flex: 1,
    maxWidth: "48.5%",
    borderRadius: radii.md,
    overflow: "hidden",
  },
  garmentWell: {
    width: "100%",
    aspectRatio: 0.78,
    alignItems: "center",
    justifyContent: "center",
  },
  cardMeta: {
    borderTopWidth: 1,
    borderTopColor: palette.hairlineFaint,
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(2.5),
  },
  cardName: { color: palette.text, fontFamily: fonts.bodyBold, fontSize: 13.5 },
  cardSlot: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 1.8,
    textTransform: "uppercase",
    marginTop: 3,
  },
});
