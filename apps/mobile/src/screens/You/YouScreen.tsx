import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

export function YouScreen() {
  const signOut = useAuth((s) => s.signOut);
  const devUserId = useAuth((s) => s.devUserId);
  const profile = useActiveProfile();

  return (
    <SafeAreaView style={styles.root}>
      <View style={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>You</Text>
        <Text style={styles.title}>{devUserId}</Text>
        <Text style={styles.body}>Active profile: {profile.ownerLabel}</Text>
        <Text style={styles.note}>
          Monetization (closet gap analysis + affiliate shopping) ships in Phase 4 once we&apos;re live.
        </Text>

        <Pressable style={styles.button} onPress={() => signOut()}>
          <Text style={styles.buttonText}>Sign out</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  body: { color: palette.textMuted, marginTop: spacing(4) },
  note: {
    color: palette.textMuted,
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    marginTop: spacing(6),
    fontSize: 13,
  },
  button: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    marginTop: spacing(8),
  },
  buttonText: { color: palette.text, fontWeight: "600" },
});
