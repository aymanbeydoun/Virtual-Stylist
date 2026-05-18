import { useNavigation } from "@react-navigation/native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { preferencesApi } from "@/api/preferences";
import type { Style } from "@/api/types";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

const STYLE_OPTIONS: { id: Style; label: string; description: string }[] = [
  {
    id: "streetwear",
    label: "Streetwear",
    description: "Oversized, sneakers, graphic pieces, hoodies / bombers.",
  },
  {
    id: "minimal",
    label: "Minimal",
    description: "Clean lines, monochrome / 2-tone, tailored basics, no logos.",
  },
  {
    id: "classic",
    label: "Classic",
    description: "Timeless silhouettes: trench, oxford, denim, loafers.",
  },
  {
    id: "smart_casual",
    label: "Smart casual",
    description: "Blazer-meets-denim, polished sneakers or loafers, no tie.",
  },
  {
    id: "preppy",
    label: "Preppy",
    description: "Collared shirts, knitwear, blazers, loafers.",
  },
  {
    id: "athleisure",
    label: "Athleisure",
    description: "Technical fabrics, sneakers, joggers / leggings.",
  },
  {
    id: "bohemian",
    label: "Bohemian",
    description: "Flowing fabrics, earth tones, layered jewellery, sandals.",
  },
  {
    id: "avant_garde",
    label: "Avant-garde",
    description: "Asymmetric, sculptural, unconventional pairings.",
  },
];

export function StylePreferenceScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const queryKey = ["stylePreference", profile.ownerKind, profile.ownerId];

  const pref = useQuery({ queryKey, queryFn: () => preferencesApi.getStyle(owner) });
  const current = pref.data?.preferred_style ?? null;

  const save = useMutation({
    mutationFn: (style: Style | null) => preferencesApi.setStyle(owner, style),
    onSuccess: (data) => {
      qc.setQueryData(queryKey, data);
      setTimeout(() => nav.goBack(), 400);
    },
    onError: (err) =>
      Alert.alert(
        "Couldn't save",
        err instanceof Error ? err.message : "Try again later.",
      ),
  });

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>Preferences</Text>
        <Text style={styles.title}>Default style</Text>
        <Text style={styles.subtitle}>
          The AI applies this style to every outfit unless you override it on the Style tab.
          You can change or clear it any time.
        </Text>

        {pref.isLoading ? (
          <ActivityIndicator color={palette.accent} style={{ marginTop: spacing(6) }} />
        ) : (
          <View style={{ marginTop: spacing(5), gap: spacing(2) }}>
            {STYLE_OPTIONS.map((opt) => {
              const active = current === opt.id;
              return (
                <Pressable
                  key={opt.id}
                  style={[styles.row, active && styles.rowActive]}
                  onPress={() => save.mutate(active ? null : opt.id)}
                  disabled={save.isPending}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.rowLabel, active && styles.rowLabelActive]}>
                      {opt.label}
                    </Text>
                    <Text style={styles.rowDesc}>{opt.description}</Text>
                  </View>
                  {active && <Text style={styles.check}>✓</Text>}
                </Pressable>
              );
            })}

            <Pressable
              style={styles.clearRow}
              onPress={() => save.mutate(null)}
              disabled={save.isPending || !current}
            >
              <Text style={[styles.clearText, !current && { opacity: 0.4 }]}>
                {current ? "Clear preference" : "No default style set"}
              </Text>
            </Pressable>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  eyebrow: {
    color: palette.textMuted,
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  subtitle: { color: palette.textMuted, marginTop: spacing(3), lineHeight: 20 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    gap: spacing(3),
    borderWidth: 1,
    borderColor: "transparent",
  },
  rowActive: { borderColor: palette.accent },
  rowLabel: { color: palette.text, fontSize: 16, fontWeight: "600" },
  rowLabelActive: { color: palette.accentDark },
  rowDesc: { color: palette.textMuted, marginTop: 2, fontSize: 13, lineHeight: 18 },
  check: { color: palette.accent, fontSize: 22, fontWeight: "700" },
  clearRow: {
    marginTop: spacing(4),
    padding: spacing(3),
    alignItems: "center",
  },
  clearText: { color: palette.textMuted, fontWeight: "600" },
});
