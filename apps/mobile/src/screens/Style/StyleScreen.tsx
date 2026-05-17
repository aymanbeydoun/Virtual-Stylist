import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { stylistApi } from "@/api/stylist";
import type { Destination, Mood, Outfit, Style } from "@/api/types";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

const ADULT_DESTINATIONS: { id: Destination; label: string }[] = [
  { id: "office", label: "Office" },
  { id: "date", label: "Date" },
  { id: "brunch", label: "Brunch" },
  { id: "casual", label: "Casual" },
  { id: "gym", label: "Gym" },
  { id: "travel", label: "Travel" },
  { id: "formal_event", label: "Formal" },
];

const KID_DESTINATIONS: { id: Destination; label: string }[] = [
  { id: "school", label: "School" },
  { id: "playground", label: "Playground" },
  { id: "casual", label: "Just hanging out" },
];

const MOODS: { id: Mood; label: string }[] = [
  { id: "confident", label: "Confident" },
  { id: "cozy", label: "Cozy" },
  { id: "edgy", label: "Edgy" },
  { id: "playful", label: "Playful" },
  { id: "minimal", label: "Minimal" },
  { id: "romantic", label: "Romantic" },
];

const KID_MOODS: { id: Mood; label: string }[] = [
  { id: "playful", label: "Playful 🎉" },
  { id: "cozy", label: "Cozy 🧸" },
  { id: "confident", label: "Hero 🦸" },
];

const STYLES: { id: Style; label: string }[] = [
  { id: "streetwear", label: "Streetwear" },
  { id: "minimal", label: "Minimal" },
  { id: "classic", label: "Classic" },
  { id: "smart_casual", label: "Smart casual" },
  { id: "preppy", label: "Preppy" },
  { id: "athleisure", label: "Athleisure" },
  { id: "bohemian", label: "Bohemian" },
  { id: "avant_garde", label: "Avant-garde" },
];

const KID_STYLES: { id: Style; label: string }[] = [
  { id: "streetwear", label: "Streetwear 🛹" },
  { id: "athleisure", label: "Sporty ⚽" },
  { id: "classic", label: "Smart 🎒" },
];

export function StyleScreen() {
  const nav = useNavigation<Nav>();
  const profile = useActiveProfile();
  const [destination, setDestination] = useState<Destination | null>(null);
  const [mood, setMood] = useState<Mood | null>(null);
  const [style, setStyle] = useState<Style | null>(null);

  const destinations = profile.isKidMode ? KID_DESTINATIONS : ADULT_DESTINATIONS;
  const moods = profile.isKidMode ? KID_MOODS : MOODS;
  const styles_ = profile.isKidMode ? KID_STYLES : STYLES;
  const accent = profile.isKidMode ? palette.kidPrimary : palette.accent;

  const generate = useMutation({
    mutationFn: () =>
      stylistApi.generate(
        { kind: profile.ownerKind, id: profile.ownerId ?? undefined },
        destination!,
        mood!,
        { style: style ?? undefined },
      ),
  });

  const outfits = generate.data?.outfits ?? [];

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>Mood &amp; Move</Text>
        <Text style={styles.title}>
          {profile.isKidMode ? `Hey ${profile.ownerLabel}!` : "What's the move?"}
        </Text>

        <Text style={styles.section}>Where to?</Text>
        <View style={styles.chips}>
          {destinations.map((d) => (
            <Chip
              key={d.id}
              label={d.label}
              active={destination === d.id}
              accent={accent}
              onPress={() => setDestination(d.id)}
            />
          ))}
        </View>

        <Text style={styles.section}>How do you feel?</Text>
        <View style={styles.chips}>
          {moods.map((m) => (
            <Chip
              key={m.id}
              label={m.label}
              active={mood === m.id}
              accent={accent}
              onPress={() => setMood(m.id)}
            />
          ))}
        </View>

        <Text style={styles.section}>
          Style <Text style={styles.sectionOptional}>(optional)</Text>
        </Text>
        <View style={styles.chips}>
          {styles_.map((s) => (
            <Chip
              key={s.id}
              label={s.label}
              active={style === s.id}
              accent={accent}
              onPress={() => setStyle(style === s.id ? null : s.id)}
            />
          ))}
        </View>

        <Pressable
          style={[styles.cta, { backgroundColor: accent }, (!destination || !mood) && { opacity: 0.4 }]}
          disabled={!destination || !mood || generate.isPending}
          onPress={() => generate.mutate()}
        >
          {generate.isPending ? (
            <ActivityIndicator color={palette.onAccent} />
          ) : (
            <View style={styles.ctaRow}>
              <Ionicons name="sparkles-outline" size={18} color={palette.onAccent} />
              <Text style={styles.ctaText}>
                {profile.isKidMode ? "Style my mission" : "Style me"}
              </Text>
            </View>
          )}
        </Pressable>

        {generate.isError && (
          <Text style={styles.error}>Couldn&apos;t generate outfits: {(generate.error as Error).message}</Text>
        )}

        {generate.data?.weather && (
          <View style={styles.weatherRow}>
            <Ionicons name="partly-sunny-outline" size={16} color={palette.textMuted} />
            <Text style={styles.weather}>
              {generate.data.weather.temp_c.toFixed(0)}°C · {generate.data.weather.condition}
            </Text>
          </View>
        )}

        {outfits.length === 0 && generate.isSuccess && (
          <Text style={styles.empty}>
            No combinations found. Try adding more items to the closet.
          </Text>
        )}

        {outfits.map((o, idx) => (
          <OutfitCard key={o.id} outfit={o} index={idx} onOpen={() => nav.navigate("OutfitDetail", { outfitId: o.id })} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function Chip({
  label,
  active,
  accent,
  onPress,
}: {
  label: string;
  active: boolean;
  accent: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.chip, active && { backgroundColor: accent, borderColor: accent }]}
      onPress={onPress}
    >
      <Text style={[styles.chipText, active && { color: palette.onAccent, fontWeight: "700" }]}>
        {label}
      </Text>
    </Pressable>
  );
}

function OutfitCard({ outfit, index, onOpen }: { outfit: Outfit; index: number; onOpen: () => void }) {
  return (
    <Pressable style={styles.outfit} onPress={onOpen}>
      <View style={styles.outfitHeader}>
        <Text style={styles.outfitTitle}>Outfit {index + 1}</Text>
        {outfit.confidence !== null && (
          <Text style={styles.outfitConfidence}>{Math.round(outfit.confidence * 100)}% match</Text>
        )}
      </View>
      {outfit.composite_image_key ? (
        <Image
          source={{
            uri: `${baseUrl}/api/v1/wardrobe/_local_read/${outfit.composite_image_key}?v=${encodeURIComponent(outfit.created_at)}`,
          }}
          style={styles.composite}
          contentFit="cover"
        />
      ) : (
        <View style={styles.outfitItems}>
          {outfit.items.map((oi) => (
            <View key={oi.item.id} style={styles.outfitItem}>
              {oi.item.thumbnail_key ? (
                <Image
                  source={{
                    uri: `${baseUrl}/api/v1/wardrobe/_local_read/${oi.item.thumbnail_key}?v=${encodeURIComponent(oi.item.created_at)}`,
                  }}
                  style={styles.outfitThumb}
                  contentFit="cover"
                />
              ) : (
                <View style={[styles.outfitThumb, { backgroundColor: palette.surfaceAlt }]} />
              )}
              <Text style={styles.outfitSlot}>{oi.slot}</Text>
            </View>
          ))}
        </View>
      )}
      {outfit.rationale && <Text style={styles.outfitRationale}>{outfit.rationale}</Text>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  section: { color: palette.text, fontSize: 16, fontWeight: "600", marginTop: spacing(6), marginBottom: spacing(3) },
  sectionOptional: { color: palette.textMuted, fontSize: 13, fontWeight: "400" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing(2) },
  chip: {
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(2),
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
    backgroundColor: palette.surface,
  },
  chipText: { color: palette.text },
  cta: { padding: spacing(4), borderRadius: radii.md, alignItems: "center", marginTop: spacing(8) },
  ctaRow: { flexDirection: "row", alignItems: "center", gap: spacing(2) },
  ctaText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
  weatherRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(2),
    marginTop: spacing(5),
  },
  weather: { color: palette.textMuted },
  outfit: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.lg,
    marginTop: spacing(4),
  },
  outfitHeader: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing(3) },
  outfitTitle: { color: palette.text, fontWeight: "700", fontSize: 16 },
  outfitConfidence: { color: palette.textMuted, fontSize: 12 },
  outfitItems: { flexDirection: "row", gap: spacing(2) },
  outfitItem: { alignItems: "center", flex: 1 },
  outfitThumb: { width: "100%", aspectRatio: 1, borderRadius: radii.md, backgroundColor: palette.surfaceAlt },
  composite: { width: "100%", aspectRatio: 1, borderRadius: radii.md, backgroundColor: palette.surfaceAlt },
  outfitSlot: { color: palette.textMuted, fontSize: 11, marginTop: 4, textTransform: "capitalize" },
  outfitRationale: { color: palette.textMuted, marginTop: spacing(3), fontStyle: "italic" },
  empty: { color: palette.textMuted, marginTop: spacing(6), textAlign: "center" },
  error: { color: palette.danger, marginTop: spacing(4) },
});
