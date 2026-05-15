import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { useMutation } from "@tanstack/react-query";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { stylistApi } from "@/api/stylist";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { palette, radii, spacing } from "@/theme";

export function OutfitDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "OutfitDetail">>();
  const nav = useNavigation();
  const { outfitId } = route.params;

  const record = useMutation({
    mutationFn: (kind: "worn" | "saved" | "skipped") => stylistApi.recordEvent(outfitId, kind),
    onSuccess: () => nav.goBack(),
  });

  return (
    <View style={styles.root}>
      <Text style={styles.title}>How&apos;d you feel about this outfit?</Text>
      <Pressable style={[styles.button, styles.primary]} onPress={() => record.mutate("worn")}>
        <Text style={styles.primaryText}>👕  Wore it today</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={() => record.mutate("saved")}>
        <Text style={styles.buttonText}>⭐  Save for later</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={() => record.mutate("skipped")}>
        <Text style={styles.buttonText}>👎  Not for me</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background, padding: spacing(5) },
  title: { color: palette.text, fontSize: 22, fontWeight: "700", marginBottom: spacing(6) },
  button: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    marginBottom: spacing(3),
  },
  buttonText: { color: palette.text, fontWeight: "600", fontSize: 16 },
  primary: { backgroundColor: palette.accent },
  primaryText: { color: palette.background, fontWeight: "700", fontSize: 16 },
});
