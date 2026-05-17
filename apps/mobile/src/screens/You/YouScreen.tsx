import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { tryonApi } from "@/api/tryon";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

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

  return (
    <SafeAreaView style={styles.root}>
      <View style={{ padding: spacing(5) }}>
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
