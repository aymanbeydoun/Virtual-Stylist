import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";

import { wardrobeApi } from "@/api/wardrobe";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";
import { isIosSimulator } from "@/utils/device";
import { ensureJpeg } from "@/utils/image";

export function AddItemScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const [status, setStatus] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async (uri: string) => {
      setStatus("Preparing photo…");
      // iPhone Camera returns HEIC by default; convert to JPEG before upload.
      const jpegUri = await ensureJpeg(uri);

      const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
      const signed = await wardrobeApi.createUploadUrl("image/jpeg", owner);

      setStatus("Uploading photo…");
      await wardrobeApi.uploadFileUri(signed.upload_url, jpegUri, "image/jpeg");

      setStatus("Tagging with AI…");
      return wardrobeApi.createItem(signed.object_key, owner);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["wardrobe"] });
      setStatus(null);
      nav.goBack();
    },
    onError: (err) => setStatus(`Failed: ${(err as Error).message}`),
  });

  const pick = (source: "camera" | "library") => {
    // Pre-check: the iOS Simulator has no camera, and launchCameraAsync's
    // behaviour there is inconsistent — sometimes it returns `canceled` with
    // no error (looks like "nothing happens"), sometimes throws. Short-circuit
    // with a visible Alert before we even try.
    if (source === "camera" && isIosSimulator()) {
      Alert.alert(
        "Camera not available in Simulator",
        "Use 'Choose from library' to pick a sample photo, or run the app on your iPhone via Expo Go to use the real camera.",
      );
      return;
    }

    // Voided so Pressable's onPress doesn't await — any error inside is caught
    // and surfaced via Alert, never bubbling as an unhandled promise.
    void (async () => {
      try {
        const perm =
          source === "camera"
            ? await ImagePicker.requestCameraPermissionsAsync()
            : await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) {
          Alert.alert(
            source === "camera" ? "Camera access denied" : "Photo library access denied",
            "Enable it in iOS Settings → Virtual Stylist.",
          );
          return;
        }
        const result =
          source === "camera"
            ? await ImagePicker.launchCameraAsync({
                quality: 0.7,
                mediaTypes: ["images"],
              })
            : await ImagePicker.launchImageLibraryAsync({
                quality: 0.7,
                mediaTypes: ["images"],
              });
        if (result.canceled) return;
        const asset = result.assets[0];
        if (asset) upload.mutate(asset.uri);
      } catch (e) {
        const m = e instanceof Error ? e.message : String(e);
        Alert.alert(`Couldn't open ${source}`, m);
      }
    })();
  };

  return (
    <View style={styles.root}>
      <Text style={styles.title}>Add an item</Text>
      <Text style={styles.subtitle}>
        We&apos;ll remove the background, tag the category, color, and pattern for you.
      </Text>
      <Pressable style={styles.primary} onPress={() => pick("camera")} disabled={upload.isPending}>
        <Ionicons name="camera-outline" size={18} color={palette.onAccent} />
        <Text style={styles.primaryText}>Take a photo</Text>
      </Pressable>
      <Pressable style={styles.secondary} onPress={() => pick("library")} disabled={upload.isPending}>
        <Ionicons name="images-outline" size={18} color={palette.text} />
        <Text style={styles.secondaryText}>Choose from library</Text>
      </Pressable>
      {upload.isPending && (
        <View style={styles.statusBox}>
          <ActivityIndicator color={palette.accent} />
          <Text style={styles.statusText}>{status}</Text>
        </View>
      )}
      {!upload.isPending && status && <Text style={styles.error}>{status}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background, padding: spacing(5) },
  title: { color: palette.text, fontSize: 24, fontWeight: "700", marginBottom: spacing(2) },
  subtitle: { color: palette.textMuted, marginBottom: spacing(6) },
  primary: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    marginBottom: spacing(3),
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing(2),
  },
  primaryText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
  secondary: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing(2),
  },
  secondaryText: { color: palette.text, fontWeight: "600", fontSize: 16 },
  statusBox: {
    marginTop: spacing(6),
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(3),
  },
  statusText: { color: palette.textMuted },
  error: { color: palette.danger, marginTop: spacing(4) },
});
