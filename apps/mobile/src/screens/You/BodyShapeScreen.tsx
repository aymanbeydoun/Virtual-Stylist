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

import { preferencesApi, type BodyShape } from "@/api/preferences";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

const SHAPES: { id: BodyShape; label: string; description: string }[] = [
  {
    id: "rectangle",
    label: "Rectangle",
    description: "Shoulders, waist and hips roughly the same width.",
  },
  {
    id: "hourglass",
    label: "Hourglass",
    description: "Defined waist with balanced shoulders and hips.",
  },
  {
    id: "pear",
    label: "Pear",
    description: "Hips wider than shoulders, defined waist.",
  },
  {
    id: "apple",
    label: "Apple",
    description: "Fuller middle, slimmer legs and arms.",
  },
  {
    id: "inverted_triangle",
    label: "Inverted triangle",
    description: "Shoulders broader than hips.",
  },
  {
    id: "athletic",
    label: "Athletic",
    description: "Defined muscle tone, straighter silhouette.",
  },
];

export function BodyShapeScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const queryKey = ["stylePreference", profile.ownerKind, profile.ownerId];

  const pref = useQuery({ queryKey, queryFn: () => preferencesApi.getStyle(owner) });
  const current = pref.data?.body_shape ?? null;

  const save = useMutation({
    mutationFn: (shape: BodyShape | null) => preferencesApi.setBodyShape(owner, shape),
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
        <Text style={styles.title}>Body shape</Text>
        <Text style={styles.subtitle}>
          The AI tailors silhouettes, fits, and necklines to your shape. You can change
          or clear this any time — it&apos;s an aid, not a label.
        </Text>

        {pref.isLoading ? (
          <ActivityIndicator color={palette.accent} style={{ marginTop: spacing(6) }} />
        ) : (
          <View style={{ marginTop: spacing(5), gap: spacing(2) }}>
            {SHAPES.map((s) => {
              const active = current === s.id;
              return (
                <Pressable
                  key={s.id}
                  style={[styles.row, active && styles.rowActive]}
                  onPress={() => save.mutate(active ? null : s.id)}
                  disabled={save.isPending}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.rowLabel, active && styles.rowLabelActive]}>
                      {s.label}
                    </Text>
                    <Text style={styles.rowDesc}>{s.description}</Text>
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
                {current ? "Clear body shape" : "No body shape set"}
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
