import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { ACCENT_THEMES, useTheme } from "@/state/theme";
import { palette, radii, spacing } from "@/theme";

export function YouScreen() {
  const signOut = useAuth((s) => s.signOut);
  const devUserId = useAuth((s) => s.devUserId);
  const profile = useActiveProfile();
  const accentId = useTheme((s) => s.accentId);
  const setAccent = useTheme((s) => s.setAccent);
  const activeColor = ACCENT_THEMES.find((t) => t.id === accentId)?.color ?? palette.accent;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>You</Text>
        <Text style={styles.title}>{devUserId}</Text>
        <Text style={styles.body}>Active profile: {profile.ownerLabel}</Text>

        <Text style={styles.section}>Theme colour</Text>
        <Text style={styles.hint}>Pick your accent — the background stays black.</Text>
        <View style={styles.swatches}>
          {ACCENT_THEMES.map((t) => {
            const selected = t.id === accentId;
            return (
              <Pressable
                key={t.id}
                style={styles.swatchWrap}
                onPress={() => setAccent(t.id)}
                accessibilityLabel={`${t.name} theme`}
              >
                <View
                  style={[
                    styles.swatch,
                    { backgroundColor: t.color },
                    selected && styles.swatchSelected,
                  ]}
                >
                  {selected && <Text style={styles.check}>✓</Text>}
                </View>
                <Text style={[styles.swatchName, selected && { color: t.color, fontWeight: "700" }]}>
                  {t.name}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Pressable style={[styles.button, { backgroundColor: activeColor }]} onPress={() => signOut()}>
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
  body: { color: palette.textMuted, marginTop: spacing(4) },
  section: { color: palette.text, fontSize: 18, fontWeight: "700", marginTop: spacing(8) },
  hint: { color: palette.textMuted, fontSize: 13, marginTop: spacing(1), marginBottom: spacing(4) },
  swatches: { flexDirection: "row", flexWrap: "wrap", gap: spacing(4) },
  swatchWrap: { alignItems: "center", width: 64 },
  swatch: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: "transparent",
  },
  swatchSelected: { borderColor: palette.text },
  check: { color: palette.background, fontWeight: "900", fontSize: 20 },
  swatchName: { color: palette.textMuted, fontSize: 12, marginTop: spacing(1) },
  button: {
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    marginTop: spacing(10),
  },
  buttonText: { color: palette.background, fontWeight: "700" },
});
