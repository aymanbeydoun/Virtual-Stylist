import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { useMutation } from "@tanstack/react-query";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { stylistApi } from "@/api/stylist";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useAccent } from "@/state/theme";
import { fonts, glass, palette, radii, spacing } from "@/theme";

export function OutfitDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "OutfitDetail">>();
  const nav = useNavigation();
  const accent = useAccent().color;
  const { outfitId } = route.params;

  const record = useMutation({
    mutationFn: (kind: "worn" | "saved" | "skipped") => stylistApi.recordEvent(outfitId, kind),
    onSuccess: () => nav.goBack(),
  });

  return (
    <View style={styles.root}>
      <Text style={styles.title}>HOW&apos;D YOU FEEL ABOUT THIS OUTFIT?</Text>
      <Pressable
        style={[styles.button, { backgroundColor: accent, borderColor: accent }]}
        onPress={() => record.mutate("worn")}
      >
        <Text style={styles.primaryText}>WORE IT TODAY</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={() => record.mutate("saved")}>
        <Text style={styles.buttonText}>SAVE FOR LATER</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={() => record.mutate("skipped")}>
        <Text style={styles.buttonText}>NOT FOR ME</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent", padding: spacing(5) },
  title: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 20,
    lineHeight: 27,
    letterSpacing: 0.5,
    marginBottom: spacing(6),
  },
  button: {
    ...glass,
    padding: spacing(4),
    borderRadius: radii.sm,
    alignItems: "center",
    marginBottom: spacing(3),
  },
  buttonText: {
    color: palette.text,
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2,
  },
  primaryText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2,
  },
});
