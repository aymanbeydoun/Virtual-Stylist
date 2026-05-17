import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { preferencesApi } from "@/api/preferences";
import { tryonApi } from "@/api/tryon";
import { wardrobeApi } from "@/api/wardrobe";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

const STYLE_LABELS: Record<string, string> = {
  streetwear: "Streetwear",
  minimal: "Minimal",
  classic: "Classic",
  smart_casual: "Smart casual",
  preppy: "Preppy",
  athleisure: "Athleisure",
  bohemian: "Bohemian",
  avant_garde: "Avant-garde",
};

const BODY_SHAPE_LABELS: Record<string, string> = {
  rectangle: "Rectangle",
  hourglass: "Hourglass",
  pear: "Pear",
  apple: "Apple",
  inverted_triangle: "Inverted triangle",
  athletic: "Athletic",
};

const GENDER_LABELS: Record<string, string> = {
  mens: "Men's",
  womens: "Women's",
};

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function YouScreen() {
  const nav = useNavigation<Nav>();
  const signOut = useAuth((s) => s.signOut);
  const displayName = useAuth((s) => s.displayName);
  const devUserId = useAuth((s) => s.devUserId);
  const profile = useActiveProfile();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const basePhoto = useQuery({
    queryKey: ["basePhoto", profile.ownerKind, profile.ownerId],
    queryFn: () => tryonApi.getBasePhoto(owner),
  });
  const hasBasePhoto = !!basePhoto.data?.base_photo_key;
  const stylePref = useQuery({
    queryKey: ["stylePreference", profile.ownerKind, profile.ownerId],
    queryFn: () => preferencesApi.getStyle(owner),
  });
  const currentStyle = stylePref.data?.preferred_style ?? null;
  const currentBodyShape = stylePref.data?.body_shape ?? null;
  const currentGender = stylePref.data?.gender ?? null;
  const insights = useQuery({
    queryKey: ["closetInsights", profile.ownerKind, profile.ownerId],
    queryFn: () => wardrobeApi.getInsights(owner),
  });
  const ins = insights.data;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5), paddingBottom: spacing(10) }}>
        <Text style={styles.eyebrow}>You</Text>
        <Text style={styles.title}>{displayName ?? "Signed in"}</Text>

        <Pressable style={styles.tryonCard} onPress={() => nav.navigate("BasePhoto")}>
          <View style={[styles.tryonDot, hasBasePhoto && { backgroundColor: "#7ce4a3" }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.tryonTitle}>
              {hasBasePhoto ? "Base photo on file" : "Add your base photo"}
            </Text>
            <Text style={styles.tryonBody}>
              {hasBasePhoto
                ? "Tap to update. We use this to render you in every outfit."
                : "One full-body photo unlocks the 'Try on me' button on every outfit."}
            </Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </Pressable>

        <Pressable style={styles.tryonCard} onPress={() => nav.navigate("StylePreference")}>
          <View style={[styles.tryonDot, currentStyle && { backgroundColor: "#7ce4a3" }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.tryonTitle}>
              {currentStyle
                ? `Default style · ${STYLE_LABELS[currentStyle] ?? currentStyle}`
                : "Set a default style"}
            </Text>
            <Text style={styles.tryonBody}>
              {currentStyle
                ? "Applied to every outfit unless you override on the Style tab."
                : "Pick a style aesthetic the AI applies by default."}
            </Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </Pressable>

        <Pressable style={styles.tryonCard} onPress={() => nav.navigate("BodyShape")}>
          <View style={[styles.tryonDot, currentBodyShape && { backgroundColor: "#7ce4a3" }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.tryonTitle}>
              {currentBodyShape
                ? `Body shape · ${BODY_SHAPE_LABELS[currentBodyShape] ?? currentBodyShape}`
                : "Set body shape"}
            </Text>
            <Text style={styles.tryonBody}>
              {currentBodyShape
                ? "Stylist tailors silhouettes + necklines to your shape."
                : "Helps the AI suggest the most flattering silhouettes."}
            </Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </Pressable>

        <Pressable style={styles.tryonCard} onPress={() => nav.navigate("Gender")}>
          <View style={[styles.tryonDot, currentGender && { backgroundColor: "#7ce4a3" }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.tryonTitle}>
              {currentGender
                ? `Gender · ${GENDER_LABELS[currentGender] ?? currentGender}`
                : "Set gender preference"}
            </Text>
            <Text style={styles.tryonBody}>
              {currentGender
                ? "Outfits stay within this gender-coded section of your closet."
                : "Prevents cross-gender items from appearing in your outfits + try-ons."}
            </Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </Pressable>

        {ins && ins.total_items > 0 && (
          <View style={styles.insightsCard}>
            <Text style={styles.insightsLabel}>Closet insights</Text>
            <Text style={styles.insightsHeadline}>
              {ins.total_items} items · {ins.worn_items} worn ·{" "}
              {ins.never_worn_items} dormant
            </Text>
            {ins.overcrowded_categories.length > 0 && (
              <View style={styles.insightsRow}>
                <Text style={styles.insightsEmoji}>📚</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.insightsHeading}>Overcrowded</Text>
                  <Text style={styles.insightsBody}>
                    {ins.overcrowded_categories
                      .slice(0, 2)
                      .map(
                        (c) =>
                          `${c.count} ${c.category.replace(".", " ")}`,
                      )
                      .join(" · ")}
                    . Lean inventory = better recommendations.
                  </Text>
                </View>
              </View>
            )}
            {ins.stale_items.length > 0 && (
              <View style={styles.insightsRow}>
                <Text style={styles.insightsEmoji}>⏳</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.insightsHeading}>
                    {ins.stale_items.length} item
                    {ins.stale_items.length === 1 ? "" : "s"} unworn 60+ days
                  </Text>
                  <Text style={styles.insightsBody}>
                    Oldest is {ins.stale_items[0]?.days_unworn ?? 0} days.
                    Consider selling, donating, or restyling.
                  </Text>
                </View>
              </View>
            )}
            {ins.underused_categories.length > 0 &&
              ins.stale_items.length === 0 && (
                <View style={styles.insightsRow}>
                  <Text style={styles.insightsEmoji}>🌱</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.insightsHeading}>
                      {ins.underused_categories.length} categories
                      untouched
                    </Text>
                    <Text style={styles.insightsBody}>
                      Generate an outfit + tap &quot;Wore it&quot; to feed
                      the stylist what you actually like.
                    </Text>
                  </View>
                </View>
              )}
          </View>
        )}

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Active profile</Text>
          <Text style={styles.cardValue}>{profile.ownerLabel}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Dev user id</Text>
          <Text style={[styles.cardValue, styles.mono]} numberOfLines={1}>
            {devUserId ?? "—"}
          </Text>
        </View>

        <Pressable style={styles.button} onPress={() => signOut()}>
          <Text style={styles.buttonText}>Sign out</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  tryonCard: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    marginTop: spacing(5),
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(3),
  },
  tryonDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: palette.accent,
  },
  tryonTitle: { color: palette.text, fontWeight: "600", marginBottom: 2 },
  tryonBody: { color: palette.textMuted, fontSize: 13, lineHeight: 18 },
  arrow: { color: palette.textMuted, fontSize: 24, fontWeight: "300" },
  card: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    marginTop: spacing(4),
  },
  cardLabel: {
    color: palette.textMuted,
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  cardValue: { color: palette.text, fontSize: 16, fontWeight: "500", marginTop: spacing(1) },
  mono: { fontFamily: "Menlo", fontSize: 12 },
  insightsCard: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    marginTop: spacing(5),
    gap: spacing(3),
  },
  insightsLabel: {
    color: palette.textMuted,
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  insightsHeadline: {
    color: palette.text,
    fontWeight: "600",
    fontSize: 16,
  },
  insightsRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing(3),
    paddingTop: spacing(1),
  },
  insightsEmoji: { fontSize: 20, marginTop: 2 },
  insightsHeading: {
    color: palette.text,
    fontWeight: "600",
    fontSize: 14,
    marginBottom: 2,
  },
  insightsBody: {
    color: palette.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  button: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    marginTop: spacing(8),
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
  },
  buttonText: { color: palette.text, fontWeight: "600" },
});
