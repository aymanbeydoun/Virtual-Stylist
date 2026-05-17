import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
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

import { tryonApi } from "@/api/tryon";
import { wardrobeApi } from "@/api/wardrobe";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";
import { isIosSimulator } from "@/utils/device";
import { ensureJpeg } from "@/utils/image";

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export function BasePhotoScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const [status, setStatus] = useState<string | null>(null);

  const queryKey = ["basePhoto", profile.ownerKind, profile.ownerId];
  const current = useQuery({
    queryKey,
    queryFn: () => tryonApi.getBasePhoto(owner),
  });

  const upload = useMutation({
    mutationFn: async (uri: string) => {
      setStatus("Preparing photo…");
      const jpegUri = await ensureJpeg(uri);
      const signed = await tryonApi.createBasePhotoUploadUrl("image/jpeg", owner);

      setStatus("Uploading photo…");
      await wardrobeApi.uploadFileUri(signed.upload_url, jpegUri, "image/jpeg");

      setStatus("Saving…");
      return tryonApi.commitBasePhoto(signed.object_key, owner);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey });
      setStatus("Saved");
      setTimeout(() => nav.goBack(), 800);
    },
    onError: (err) => setStatus(`Failed: ${(err as Error).message}`),
  });

  const pick = (source: "camera" | "library") => {
    if (source === "camera" && isIosSimulator()) {
      Alert.alert(
        "Camera not available in Simulator",
        "Use 'Choose from library' to pick a sample photo, or run the app on your iPhone via Expo Go to use the real camera.",
      );
      return;
    }
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
                quality: 0.85,
                mediaTypes: ["images"],
              })
            : await ImagePicker.launchImageLibraryAsync({
                quality: 0.85,
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

  const existingKey = current.data?.base_photo_key;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>Virtual try-on</Text>
        <Text style={styles.title}>Your base photo</Text>
        <Text style={styles.subtitle}>
          One full-body photo, plain background, front-facing. The AI uses this to render you
          wearing every outfit. You can replace it any time.
        </Text>

        {existingKey ? (
          <View style={styles.currentBox}>
            <Image
              source={{
                uri: `${baseUrl}/api/v1/wardrobe/_local_read/${existingKey}?v=${profile.ownerId ?? "user"}`,
              }}
              style={styles.preview}
              contentFit="cover"
            />
            <Text style={styles.currentLabel}>Current base photo</Text>
          </View>
        ) : (
          <View style={styles.tips}>
            <Text style={styles.tipTitle}>For best results</Text>
            <Text style={styles.tip}>• Stand against a plain wall</Text>
            <Text style={styles.tip}>• Wear fitted clothing (so the AI sees your shape)</Text>
            <Text style={styles.tip}>• Arms slightly away from body</Text>
            <Text style={styles.tip}>• Camera at chest height, full body in frame</Text>
          </View>
        )}

        <Pressable
          style={styles.primary}
          onPress={() => pick("camera")}
          disabled={upload.isPending}
        >
          <Ionicons name="camera-outline" size={18} color={palette.onAccent} />
          <Text style={styles.primaryText}>Take a photo</Text>
        </Pressable>
        <Pressable
          style={styles.secondary}
          onPress={() => pick("library")}
          disabled={upload.isPending}
        >
          <Ionicons name="images-outline" size={18} color={palette.text} />
          <Text style={styles.secondaryText}>Choose from library</Text>
        </Pressable>

        {upload.isPending && (
          <View style={styles.statusBox}>
            <ActivityIndicator color={palette.accent} />
            <Text style={styles.statusText}>{status}</Text>
          </View>
        )}
        {!upload.isPending && status && (
          <Text style={styles.statusText}>{status}</Text>
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
  currentBox: {
    marginTop: spacing(5),
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    padding: spacing(3),
    alignItems: "center",
  },
  preview: { width: "100%", aspectRatio: 3 / 4, borderRadius: radii.md },
  currentLabel: { color: palette.textMuted, marginTop: spacing(2), fontSize: 12 },
  tips: {
    marginTop: spacing(5),
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    gap: spacing(1),
  },
  tipTitle: { color: palette.text, fontWeight: "600", marginBottom: spacing(2) },
  tip: { color: palette.textMuted, fontSize: 13 },
  primary: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    marginTop: spacing(6),
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
    marginTop: spacing(3),
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
  statusText: { color: palette.textMuted, marginTop: spacing(4) },
});
