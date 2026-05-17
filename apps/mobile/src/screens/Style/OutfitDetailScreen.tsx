import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { stylistApi } from "@/api/stylist";
import { tryonApi } from "@/api/tryon";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export function OutfitDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "OutfitDetail">>();
  const nav = useNavigation<Nav>();
  const { outfitId } = route.params;

  // Poll the latest try-on while it's pending so the rendered image streams in
  // as soon as the worker writes it. 404 means no tryon yet — query returns
  // null and we show the CTA instead.
  const tryon = useQuery({
    queryKey: ["tryon", outfitId],
    queryFn: async () => {
      try {
        return await tryonApi.getLatestTryon(outfitId);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "";
        if (/404|no tryon/i.test(msg)) return null;
        throw e;
      }
    },
    refetchInterval: (q) => {
      const data = q.state.data;
      return data && data.status === "pending" ? 2500 : false;
    },
  });

  const requestTryon = useMutation({
    mutationFn: () => tryonApi.requestTryon(outfitId),
    onSuccess: () => tryon.refetch(),
    onError: (err) => {
      const m = err instanceof Error ? err.message : "";
      if (/412|base photo/i.test(m)) {
        Alert.alert(
          "Add a base photo first",
          "Open You → Add your base photo to enable try-on.",
          [
            { text: "Later", style: "cancel" },
            { text: "Add now", onPress: () => nav.navigate("BasePhoto") },
          ],
        );
        return;
      }
      Alert.alert("Try-on failed", m || "Try again later.");
    },
  });

  const record = useMutation({
    mutationFn: (kind: "worn" | "saved" | "skipped") => stylistApi.recordEvent(outfitId, kind),
    onSuccess: () => nav.goBack(),
  });

  const t = tryon.data;

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: spacing(5) }}>
      <View style={styles.tryonBox}>
        {!t && (
          <View style={styles.tryonPlaceholder}>
            <Text style={styles.tryonPlaceholderText}>
              See yourself wearing this outfit
            </Text>
            <Pressable
              style={[styles.button, styles.primary]}
              onPress={() => requestTryon.mutate()}
              disabled={requestTryon.isPending}
            >
              {requestTryon.isPending ? (
                <ActivityIndicator color={palette.background} />
              ) : (
                <Text style={styles.primaryText}>✨  Try on me</Text>
              )}
            </Pressable>
          </View>
        )}

        {t?.status === "pending" && (
          <View style={styles.tryonPlaceholder}>
            <ActivityIndicator color={palette.accent} size="large" />
            <Text style={styles.tryonPlaceholderText}>
              Rendering you in this look… 10-15s
            </Text>
          </View>
        )}

        {t?.status === "ready" && t.rendered_image_key && (
          <View>
            <Image
              source={{
                uri: `${baseUrl}/api/v1/wardrobe/_local_read/${t.rendered_image_key}?v=${t.id}`,
              }}
              style={styles.tryonImage}
              contentFit="cover"
            />
            <Pressable
              style={styles.regenButton}
              onPress={() => requestTryon.mutate()}
              disabled={requestTryon.isPending}
            >
              <Text style={styles.regenText}>↻  Render again</Text>
            </Pressable>
          </View>
        )}

        {t?.status === "failed" && (
          <View style={styles.tryonPlaceholder}>
            <Text style={styles.errorText}>
              Couldn&apos;t render this look: {t.error_message ?? "unknown error"}
            </Text>
            <Pressable
              style={[styles.button, styles.primary]}
              onPress={() => requestTryon.mutate()}
              disabled={requestTryon.isPending}
            >
              <Text style={styles.primaryText}>Try again</Text>
            </Pressable>
          </View>
        )}
      </View>

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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  tryonBox: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    overflow: "hidden",
    marginBottom: spacing(6),
  },
  tryonPlaceholder: {
    padding: spacing(8),
    alignItems: "center",
    gap: spacing(4),
  },
  tryonPlaceholderText: {
    color: palette.text,
    fontSize: 16,
    fontWeight: "500",
    textAlign: "center",
  },
  tryonImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: palette.surfaceAlt,
  },
  regenButton: { padding: spacing(3), alignItems: "center" },
  regenText: { color: palette.textMuted, fontWeight: "600" },
  title: { color: palette.text, fontSize: 22, fontWeight: "700", marginBottom: spacing(4) },
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
  errorText: { color: palette.danger, textAlign: "center" },
});
