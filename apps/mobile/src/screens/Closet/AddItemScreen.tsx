import { useNavigation } from "@react-navigation/native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { wardrobeApi } from "@/api/wardrobe";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

export function AddItemScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const [status, setStatus] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async (uri: string) => {
      setStatus("Preparing upload…");
      const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
      const signed = await wardrobeApi.createUploadUrl("image/jpeg", owner);

      setStatus("Uploading photo…");
      await wardrobeApi.uploadFileUri(signed.upload_url, uri, "image/jpeg");

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
    // Voided so Pressable's onPress doesn't await — any error inside is caught
    // and surfaced via setStatus, never bubbling as an unhandled promise.
    void (async () => {
      try {
        const perm =
          source === "camera"
            ? await ImagePicker.requestCameraPermissionsAsync()
            : await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) {
          setStatus(
            source === "camera"
              ? "Camera access denied. Enable it in Settings → Virtual Stylist."
              : "Photo library access denied.",
          );
          return;
        }
        const result =
          source === "camera"
            ? await ImagePicker.launchCameraAsync({
                quality: 0.7,
                mediaTypes: ImagePicker.MediaTypeOptions.Images,
              })
            : await ImagePicker.launchImageLibraryAsync({
                quality: 0.7,
                mediaTypes: ImagePicker.MediaTypeOptions.Images,
              });
        if (result.canceled) return;
        const asset = result.assets[0];
        if (asset) upload.mutate(asset.uri);
      } catch (e) {
        const m = e instanceof Error ? e.message : String(e);
        // iOS Simulator has no real camera — launchCameraAsync throws.
        if (source === "camera" && /no.*camera|unavailable|simulator/i.test(m)) {
          setStatus("The iOS Simulator doesn't have a camera. Use 'Choose from library' instead.");
        } else {
          setStatus(`Couldn't open ${source}: ${m}`);
        }
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
        <Text style={styles.primaryText}>📷 Take a photo</Text>
      </Pressable>
      <Pressable style={styles.secondary} onPress={() => pick("library")} disabled={upload.isPending}>
        <Text style={styles.secondaryText}>🖼  Choose from library</Text>
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
  },
  primaryText: { color: palette.background, fontWeight: "700", fontSize: 16 },
  secondary: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
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
