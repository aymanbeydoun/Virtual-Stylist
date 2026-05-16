import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

export function YouScreen() {
  const signOut = useAuth((s) => s.signOut);
  const displayName = useAuth((s) => s.displayName);
  const devUserId = useAuth((s) => s.devUserId);
  const profile = useActiveProfile();

  return (
    <SafeAreaView style={styles.root}>
      <View style={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>You</Text>
        <Text style={styles.title}>{displayName ?? "Signed in"}</Text>

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
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
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
