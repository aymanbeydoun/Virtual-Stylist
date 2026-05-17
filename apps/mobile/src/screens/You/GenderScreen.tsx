import { useNavigation } from "@react-navigation/native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { preferencesApi, type Gender } from "@/api/preferences";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

const OPTIONS: { id: Gender; label: string; description: string }[] = [
  {
    id: "mens",
    label: "Men's",
    description:
      "Filter outfit suggestions to men's-coded items in your closet.",
  },
  {
    id: "womens",
    label: "Women's",
    description:
      "Filter outfit suggestions to women's-coded items in your closet.",
  },
];

/**
 * Gender preference picker.
 *
 * Hard-filters the candidate item pool for outfit composition so the
 * AI can't suggest cross-gender garments — which previously broke try-on
 * because Gemini's image-edit biases toward the garment's coded gender,
 * generating a person of that gender rather than preserving the user.
 *
 * When unset, the backend falls back to auto-detection: if >=70% of the
 * user's closet has one gender prefix, that's used as a soft signal.
 * Mixed closets (50/50 from seeded data) need this explicit setting.
 */
export function GenderScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const queryKey = ["stylePreference", profile.ownerKind, profile.ownerId];

  const pref = useQuery({ queryKey, queryFn: () => preferencesApi.getStyle(owner) });
  const current = pref.data?.gender ?? null;

  const save = useMutation({
    mutationFn: (g: Gender | null) => preferencesApi.setGender(owner, g),
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
        <Text style={styles.title}>Gender preference</Text>
        <Text style={styles.subtitle}>
          Filters outfit suggestions to one gender-coded section of your closet.
          Without it, the stylist sometimes picks cross-gender items — which can
          confuse try-on into rendering the wrong person. Accessories and
          jewelry are kept either way.
        </Text>

        {pref.isLoading ? (
          <ActivityIndicator
            color={palette.accent}
            style={{ marginTop: spacing(6) }}
          />
        ) : (
          <View style={{ marginTop: spacing(5), gap: spacing(2) }}>
            {OPTIONS.map((o) => {
              const active = current === o.id;
              return (
                <Pressable
                  key={o.id}
                  style={[styles.row, active && styles.rowActive]}
                  onPress={() => save.mutate(active ? null : o.id)}
                  disabled={save.isPending}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.rowLabel, active && styles.rowLabelActive]}>
                      {o.label}
                    </Text>
                    <Text style={styles.rowDesc}>{o.description}</Text>
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
                {current ? "Clear preference (auto-detect)" : "No preference (auto-detect)"}
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
  clearRow: { marginTop: spacing(4), padding: spacing(3), alignItems: "center" },
  clearText: { color: palette.textMuted, fontWeight: "600" },
});
