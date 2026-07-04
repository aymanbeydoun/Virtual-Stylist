import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ChatIcon, ChevronIcon, PenIcon } from "@/components/icons";
import { LevelBadge } from "@/components/LevelBadge";
import { OutfitCanvas } from "@/components/OutfitCanvas";
import { RatingTier } from "@/components/RatingTier";
import { RenameStylistModal } from "@/components/RenameStylistModal";
import {
  KID_OCCASIONS,
  KID_VIBES,
  OCCASIONS,
  VIBES,
  type OccasionOption,
  type VibeOption,
} from "@/data/style";
import { stailMe, type DemoOutfit } from "@/demo/stylist";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { useStylist } from "@/state/stylist";
import { useAccent } from "@/state/theme";
import { fonts, glass, palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function StyleScreen() {
  const nav = useNavigation<Nav>();
  const profile = useActiveProfile();
  const aiName = useStylist((s) => s.name);
  const { width } = useWindowDimensions();
  const [vibe, setVibe] = useState<VibeOption | null>(null);
  const [occasion, setOccasion] = useState<OccasionOption | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [outfits, setOutfits] = useState<DemoOutfit[] | null>(null);

  const vibes = profile.isKidMode ? KID_VIBES : VIBES;
  const occasions = profile.isKidMode ? KID_OCCASIONS : OCCASIONS;
  const accent = useAccent().color;
  const ready = Boolean(vibe && occasion);

  // Lookbook cards page horizontally, peeking the next look.
  const cardWidth = width - spacing(14);
  const snap = cardWidth + spacing(3);

  const onStaileMe = () => {
    if (!vibe || !occasion) return;
    setLoading(true);
    setOutfits(null);
    // Small "thinking" beat so it feels like the stylist is working.
    setTimeout(() => {
      setOutfits(stailMe(vibe.label, occasion.label));
      setLoading(false);
    }, 700);
  };

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingVertical: spacing(5) }}>
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>STaiLE ME</Text>
            <Text style={styles.title}>
              {profile.isKidMode ? `HEY ${profile.ownerLabel.toUpperCase()}!` : "WHAT'S THE MOVE?"}
            </Text>
          </View>
          <LevelBadge onPress={() => nav.navigate("Status")} />
        </View>

        <Text style={styles.section}>WHAT&apos;S THE VIBE?</Text>
        <View style={styles.chips}>
          {vibes.map((v) => (
            <Chip
              key={v.id}
              label={v.label}
              active={vibe?.id === v.id}
              accent={accent}
              onPress={() => setVibe(v)}
            />
          ))}
        </View>

        <Text style={styles.section}>WHERE ARE YOU GOING?</Text>
        <View style={styles.chips}>
          {occasions.map((o) => (
            <Chip
              key={o.id}
              label={o.label}
              active={occasion?.id === o.id}
              accent={accent}
              onPress={() => setOccasion(o)}
            />
          ))}
        </View>

        <Pressable
          style={[
            styles.cta,
            { backgroundColor: accent, shadowColor: accent },
            !ready && { opacity: 0.35, shadowOpacity: 0 },
          ]}
          disabled={!ready || loading}
          onPress={onStaileMe}
        >
          {loading ? (
            <ActivityIndicator color={palette.background} />
          ) : (
            <Text style={styles.ctaText}>
              {profile.isKidMode ? "STaiLE MY MISSION" : "STaiLE ME"}
            </Text>
          )}
        </Pressable>

        {loading && (
          <Text style={styles.thinking}>{aiName.toUpperCase()} IS PUTTING LOOKS TOGETHER…</Text>
        )}

        {outfits && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            snapToInterval={snap}
            decelerationRate="fast"
            contentContainerStyle={{
              paddingHorizontal: spacing(5),
              gap: spacing(3),
              paddingTop: spacing(5),
            }}
          >
            {outfits.map((o, idx) => (
              <OutfitCard
                key={o.id}
                outfit={o}
                index={idx}
                width={cardWidth}
                aiName={aiName}
                accent={accent}
                onEditName={() => setRenameOpen(true)}
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
        )}
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
      style={[
        styles.chip,
        active && {
          borderColor: accent,
          shadowColor: accent,
          shadowOpacity: 0.55,
          shadowRadius: 8,
          shadowOffset: { width: 0, height: 0 },
        },
      ]}
      onPress={onPress}
    >
      <Text style={[styles.chipText, active && { color: accent, fontFamily: fonts.bodyBold }]}>
        {label.toUpperCase()}
      </Text>
    </Pressable>
  );
}

function OutfitCard({
  outfit,
  index,
  width,
  aiName,
  accent,
  onChat,
  onEditName,
}: {
  outfit: DemoOutfit;
  index: number;
  width: number;
  aiName: string;
  accent: string;
  onChat: () => void;
  onEditName: () => void;
}) {
  const [rating, setRating] = useState<number | null>(null);

  return (
    <View style={[styles.outfit, { width }]}>
      <View style={styles.outfitHeader}>
        <Text style={styles.outfitTitle}>OUTFIT {String(index + 1).padStart(2, "0")}</Text>
        <Text style={[styles.outfitConfidence, { color: accent }]}>
          {Math.round(outfit.confidence * 100)}% MATCH
        </Text>
      </View>

      {/* Lookbook collage — pieces overlap like a curated sketch. */}
      <OutfitCanvas items={outfit.items} />
      <Text style={styles.pieces} numberOfLines={1}>
        {outfit.items.map((i) => i.name.toUpperCase()).join("  ·  ")}
      </Text>

      <View style={styles.divider} />

      <RatingTier value={rating} accent={accent} onChange={setRating} />

      {/* AI's rationale */}
      <Text style={styles.rationale}>
        <Text style={[styles.rationaleName, { color: accent }]}>{aiName}&apos;s choice — </Text>
        {outfit.rationale}
      </Text>

      {/* Premium chat action bar + rename */}
      <View style={styles.chatRow}>
        <Pressable style={styles.chatBtn} onPress={onChat}>
          <View style={[styles.chatIconWell, { borderColor: accent }]}>
            <ChatIcon size={15} color={accent} />
          </View>
          <Text style={styles.chatBtnText}>CHAT TO {aiName.toUpperCase()}</Text>
          <ChevronIcon size={15} color={palette.textMuted} />
        </Pressable>
        <Pressable
          style={styles.penBtn}
          onPress={onEditName}
          accessibilityLabel="Rename your stylist"
        >
          <PenIcon size={16} color={palette.text} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(3),
    marginBottom: spacing(2),
    paddingHorizontal: spacing(5),
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
    fontSize: 24,
    marginTop: 6,
    letterSpacing: 0.5,
    lineHeight: 30,
  },
  section: {
    color: palette.text,
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2,
    marginTop: spacing(6),
    marginBottom: spacing(3),
    paddingHorizontal: spacing(5),
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing(2),
    paddingHorizontal: spacing(5),
  },
  // Dark matte chips — clean type, prominent border when active.
  chip: {
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(2.5),
    borderRadius: radii.sm,
    borderWidth: 1.5,
    borderColor: palette.hairline,
    backgroundColor: palette.panel,
  },
  chipText: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11.5,
    letterSpacing: 1.2,
  },
  cta: {
    padding: spacing(4),
    borderRadius: radii.sm,
    alignItems: "center",
    marginTop: spacing(8),
    marginHorizontal: spacing(5),
    shadowOpacity: 0.45,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 2 },
  },
  ctaText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 15,
    letterSpacing: 2.5,
  },
  thinking: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 10.5,
    letterSpacing: 1.8,
    textAlign: "center",
    marginTop: spacing(4),
  },
  outfit: {
    ...glass,
    padding: spacing(4),
    borderRadius: radii.lg,
  },
  outfitHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing(3),
  },
  outfitTitle: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 15,
    letterSpacing: 1,
  },
  outfitConfidence: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5 },
  pieces: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 9,
    letterSpacing: 1.2,
    marginTop: spacing(2.5),
  },
  divider: {
    height: 1,
    backgroundColor: palette.hairlineFaint,
    marginVertical: spacing(3.5),
  },
  rationale: {
    color: palette.text,
    fontFamily: fonts.body,
    fontSize: 13.5,
    marginTop: spacing(4),
    lineHeight: 20,
  },
  rationaleName: { fontFamily: fonts.bodyBold },
  chatRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(2),
    marginTop: spacing(4),
  },
  chatBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(2.5),
    backgroundColor: palette.surfaceAlt,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: radii.md,
    paddingVertical: spacing(2.5),
    paddingHorizontal: spacing(3),
  },
  chatIconWell: {
    width: 30,
    height: 30,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  chatBtnText: {
    flex: 1,
    color: palette.text,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    letterSpacing: 1.5,
  },
  penBtn: {
    width: 46,
    height: 46,
    borderRadius: radii.md,
    backgroundColor: palette.surfaceAlt,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: "center",
    justifyContent: "center",
  },
});
