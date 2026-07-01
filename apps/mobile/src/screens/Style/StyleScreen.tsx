import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { stylistApi } from "@/api/stylist";
import type { Outfit } from "@/api/types";
import { LevelBadge } from "@/components/LevelBadge";
import { RenameStylistModal } from "@/components/RenameStylistModal";
import { RATINGS } from "@/data/ratings";
import {
  KID_OCCASIONS,
  KID_VIBES,
  OCCASIONS,
  VIBES,
  type OccasionOption,
  type VibeOption,
} from "@/data/style";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { useStylist } from "@/state/stylist";
import { palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export function StyleScreen() {
  const nav = useNavigation<Nav>();
  const profile = useActiveProfile();
  const aiName = useStylist((s) => s.name);
  const [vibe, setVibe] = useState<VibeOption | null>(null);
  const [occasion, setOccasion] = useState<OccasionOption | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);

  const vibes = profile.isKidMode ? KID_VIBES : VIBES;
  const occasions = profile.isKidMode ? KID_OCCASIONS : OCCASIONS;
  const accent = profile.isKidMode ? palette.kidPrimary : palette.accent;

  const generate = useMutation({
    mutationFn: () =>
      stylistApi.generate(
        { kind: profile.ownerKind, id: profile.ownerId ?? undefined },
        occasion!.destination,
        vibe!.mood,
        `Vibe: ${vibe!.label}. Occasion: ${occasion!.label}.`,
      ),
  });

  const outfits = generate.data?.outfits ?? [];
  const ready = Boolean(vibe && occasion);

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>Stail Me</Text>
            <Text style={styles.title}>
              {profile.isKidMode ? `Hey ${profile.ownerLabel}!` : "What's the move?"}
            </Text>
          </View>
          <LevelBadge onPress={() => nav.navigate("Status")} />
        </View>

        <Text style={styles.section}>What&apos;s the vibe?</Text>
        <View style={styles.chips}>
          {vibes.map((v) => (
            <Chip
              key={v.id}
              label={`${v.emoji} ${v.label}`}
              active={vibe?.id === v.id}
              accent={accent}
              onPress={() => setVibe(v)}
            />
          ))}
        </View>

        <Text style={styles.section}>Where are you going?</Text>
        <View style={styles.chips}>
          {occasions.map((o) => (
            <Chip
              key={o.id}
              label={`${o.emoji} ${o.label}`}
              active={occasion?.id === o.id}
              accent={accent}
              onPress={() => setOccasion(o)}
            />
          ))}
        </View>

        <Pressable
          style={[styles.cta, { backgroundColor: accent }, !ready && { opacity: 0.4 }]}
          disabled={!ready || generate.isPending}
          onPress={() => generate.mutate()}
        >
          {generate.isPending ? (
            <ActivityIndicator color={palette.background} />
          ) : (
            <Text style={styles.ctaText}>
              {profile.isKidMode ? "Style my mission ✨" : "Style me"}
            </Text>
          )}
        </Pressable>

        {generate.isError && (
          <Text style={styles.error}>
            Couldn&apos;t generate outfits: {(generate.error as Error).message}
          </Text>
        )}

        {generate.data?.weather && (
          <Text style={styles.weather}>
            🌤  {generate.data.weather.temp_c.toFixed(0)}°C · {generate.data.weather.condition}
          </Text>
        )}

        {outfits.length === 0 && generate.isSuccess && (
          <Text style={styles.empty}>
            No combinations found. Try adding more items to the closet.
          </Text>
        )}

        {outfits.map((o, idx) => (
          <OutfitCard
            key={o.id}
            outfit={o}
            index={idx}
            aiName={aiName}
            accent={accent}
            onEditName={() => setRenameOpen(true)}
            onOpen={() => nav.navigate("OutfitDetail", { outfitId: o.id })}
            onChat={() =>
              nav.navigate("StylistChat", {
                outfitId: o.id,
                context: `Outfit ${idx + 1}${
                  vibe && occasion ? ` — ${vibe.label}, ${occasion.label}` : ""
                }`,
              })
            }
          />
        ))}
      </ScrollView>

      <RenameStylistModal
        visible={renameOpen}
        onClose={() => setRenameOpen(false)}
        accent={accent}
      />
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
      <Text style={[styles.chipText, active && { color: palette.background, fontWeight: "700" }]}>
        {label}
      </Text>
    </Pressable>
  );
}

function OutfitCard({
  outfit,
  index,
  aiName,
  accent,
  onOpen,
  onChat,
  onEditName,
}: {
  outfit: Outfit;
  index: number;
  aiName: string;
  accent: string;
  onOpen: () => void;
  onChat: () => void;
  onEditName: () => void;
}) {
  const [rating, setRating] = useState<number | null>(null);

  const onRate = (value: number) => {
    setRating(value);
    // Feed the choice back to the backend so the stylist learns preferences.
    stylistApi.recordEvent(outfit.id, value >= 4 ? "saved" : "skipped").catch(() => {});
  };

  return (
    <View style={styles.outfit}>
      <Pressable onPress={onOpen}>
        <View style={styles.outfitHeader}>
          <Text style={styles.outfitTitle}>Outfit {index + 1}</Text>
          {outfit.confidence !== null && (
            <Text style={styles.outfitConfidence}>{Math.round(outfit.confidence * 100)}% match</Text>
          )}
        </View>
        <View style={styles.outfitItems}>
          {outfit.items.map((oi) => (
            <View key={oi.item.id} style={styles.outfitItem}>
              {oi.item.thumbnail_key ? (
                <Image
                  source={{ uri: `${baseUrl}/api/v1/wardrobe/_local_read/${oi.item.thumbnail_key}` }}
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
      </Pressable>

      {/* Rate the AI's choice */}
      <Text style={styles.rateLabel}>How do you like it?</Text>
      <View style={styles.ratings}>
        {RATINGS.map((r) => (
          <Pressable
            key={r.value}
            onPress={() => onRate(r.value)}
            style={[styles.rating, rating === r.value && { backgroundColor: accent }]}
            accessibilityLabel={r.label}
          >
            <Text style={styles.ratingEmoji}>{r.emoji}</Text>
          </Pressable>
        ))}
      </View>

      {/* AI's rationale */}
      {outfit.rationale && (
        <Text style={styles.rationale}>
          <Text style={[styles.rationaleName, { color: accent }]}>{aiName}&apos;s choice: </Text>
          {outfit.rationale}
        </Text>
      )}

      {/* Chat + rename */}
      <View style={styles.chatRow}>
        <Pressable style={[styles.chatBtn, { borderColor: accent }]} onPress={onChat}>
          <Text style={[styles.chatBtnText, { color: accent }]}>💬 Chat to {aiName}</Text>
        </Pressable>
        <Pressable
          style={styles.penBtn}
          onPress={onEditName}
          accessibilityLabel="Rename your stylist"
        >
          <Text style={styles.penIcon}>✏️</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  header: { flexDirection: "row", alignItems: "center", gap: spacing(3), marginBottom: spacing(2) },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  section: { color: palette.text, fontSize: 16, fontWeight: "600", marginTop: spacing(6), marginBottom: spacing(3) },
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
  ctaText: { color: palette.background, fontWeight: "700", fontSize: 16 },
  weather: { color: palette.textMuted, marginTop: spacing(5) },
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
  outfitSlot: { color: palette.textMuted, fontSize: 11, marginTop: 4, textTransform: "capitalize" },
  rateLabel: { color: palette.textMuted, fontSize: 12, marginTop: spacing(4), marginBottom: spacing(2) },
  ratings: { flexDirection: "row", justifyContent: "space-between", gap: spacing(1) },
  rating: {
    flex: 1,
    aspectRatio: 1,
    maxWidth: 48,
    borderRadius: radii.md,
    backgroundColor: palette.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  ratingEmoji: { fontSize: 20 },
  rationale: { color: palette.text, marginTop: spacing(4), lineHeight: 20 },
  rationaleName: { fontWeight: "700" },
  chatRow: { flexDirection: "row", alignItems: "center", gap: spacing(2), marginTop: spacing(4) },
  chatBtn: {
    flex: 1,
    borderWidth: 1.5,
    borderRadius: radii.md,
    paddingVertical: spacing(3),
    alignItems: "center",
  },
  chatBtnText: { fontWeight: "700" },
  penBtn: {
    width: 44,
    height: 44,
    borderRadius: radii.md,
    backgroundColor: palette.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  penIcon: { fontSize: 18 },
  empty: { color: palette.textMuted, marginTop: spacing(6), textAlign: "center" },
  error: { color: palette.danger, marginTop: spacing(4) },
});
