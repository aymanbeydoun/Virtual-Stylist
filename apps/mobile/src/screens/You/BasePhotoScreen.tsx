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

import type { Angle } from "@/api/types";
import { ANGLES, ANGLE_HINT, ANGLE_LABEL } from "@/api/types";
import { tryonApi } from "@/api/tryon";
import { wardrobeApi } from "@/api/wardrobe";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";
import { isIosSimulator } from "@/utils/device";
import { ensureJpeg } from "@/utils/image";

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Multi-angle base photo capture.
 *
 * For "VERY REAL" multi-angle try-on, we need a real photo at each angle.
 * The screen renders 4 slots — front, 3/4 left, back, 3/4 right — each can
 * be filled independently. Front is required (try-on falls back to it if
 * the other angles aren't uploaded yet); the others unlock the carousel
 * playback once present.
 */
export function BasePhotoScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const [status, setStatus] = useState<string | null>(null);
  const [busyAngle, setBusyAngle] = useState<Angle | null>(null);

  const queryKey = ["basePhotoSet", profile.ownerKind, profile.ownerId];
  const photos = useQuery({
    queryKey,
    queryFn: () => tryonApi.getBasePhotoSet(owner),
  });

  const upload = useMutation({
    mutationFn: async ({ uri, angle }: { uri: string; angle: Angle }) => {
      setStatus("Preparing photo…");
      const jpegUri = await ensureJpeg(uri);
      const signed = await tryonApi.createBasePhotoUploadUrl(
        "image/jpeg",
        owner,
      );
      setStatus("Uploading…");
      await wardrobeApi.uploadFileUri(signed.upload_url, jpegUri, "image/jpeg");
      setStatus("Saving…");
      return tryonApi.commitBasePhoto(signed.object_key, owner, angle);
    },
    onMutate: ({ angle }) => {
      setBusyAngle(angle);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey });
      setStatus(null);
      setBusyAngle(null);
    },
    onError: (err) => {
      setStatus(`Failed: ${(err as Error).message}`);
      setBusyAngle(null);
    },
  });

  const pickForAngle = (angle: Angle) => {
    Alert.alert(
      `Photo for ${ANGLE_LABEL[angle]}`,
      ANGLE_HINT[angle],
      [
        { text: "Cancel", style: "cancel" },
        { text: "Photo library", onPress: () => pick(angle, "library") },
        { text: "Camera", onPress: () => pick(angle, "camera") },
      ],
    );
  };

  const pick = (angle: Angle, source: "camera" | "library") => {
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
        if (asset) upload.mutate({ uri: asset.uri, angle });
      } catch (e) {
        const m = e instanceof Error ? e.message : String(e);
        Alert.alert(`Couldn't open ${source}`, m);
      }
    })();
  };

  const keys = photos.data?.base_photo_keys ?? {};
  const completed = ANGLES.filter((a) => keys[a]).length;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5), paddingBottom: spacing(10) }}>
        <Text style={styles.eyebrow}>Virtual try-on</Text>
        <Text style={styles.title}>Your photo, four angles</Text>
        <Text style={styles.subtitle}>
          The AI uses these to render you wearing every outfit from every angle.
          One required (front); add 3/4 left, back, and 3/4 right to unlock the
          full 360° carousel.
        </Text>

        <View style={styles.progress}>
          <Text style={styles.progressText}>
            {completed} of {ANGLES.length} angles captured
          </Text>
          <View style={styles.progressBar}>
            <View
              style={[
                styles.progressFill,
                { width: `${(completed / ANGLES.length) * 100}%` },
              ]}
            />
          </View>
        </View>

        <View style={styles.tips}>
          <Text style={styles.tipTitle}>For best results</Text>
          <Text style={styles.tip}>• Stand against a plain wall, even lighting</Text>
          <Text style={styles.tip}>• Wear fitted clothing so the AI sees your shape</Text>
          <Text style={styles.tip}>• Arms slightly away from your body</Text>
          <Text style={styles.tip}>• Full body in frame, camera at chest height</Text>
        </View>

        <View style={styles.grid}>
          {ANGLES.map((angle) => {
            const key = keys[angle];
            const isBusy = busyAngle === angle;
            return (
              <Pressable
                key={angle}
                style={[styles.cell, !!key && styles.cellFilled]}
                onPress={() => pickForAngle(angle)}
                disabled={isBusy}
              >
                {key ? (
                  <Image
                    source={{
                      uri: `${baseUrl}/api/v1/wardrobe/_local_read/${key}?v=${angle}`,
                    }}
                    style={styles.thumb}
                    contentFit="cover"
                  />
                ) : (
                  <View style={styles.empty}>
                    <Ionicons
                      name="add-circle-outline"
                      size={32}
                      color={palette.textMuted}
                    />
                  </View>
                )}
                <View style={styles.label}>
                  <Text style={styles.labelTitle}>{ANGLE_LABEL[angle]}</Text>
                  {isBusy && (
                    <ActivityIndicator color={palette.accent} size="small" />
                  )}
                </View>
              </Pressable>
            );
          })}
        </View>

        {status && <Text style={styles.statusText}>{status}</Text>}

        {completed > 0 && (
          <Pressable
            style={styles.doneButton}
            onPress={() => nav.goBack()}
          >
            <Text style={styles.doneText}>Done</Text>
          </Pressable>
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
  subtitle: {
    color: palette.textMuted,
    marginTop: spacing(3),
    lineHeight: 20,
  },
  progress: { marginTop: spacing(5), marginBottom: spacing(2) },
  progressText: {
    color: palette.textMuted,
    fontSize: 12,
    marginBottom: spacing(2),
  },
  progressBar: {
    height: 4,
    backgroundColor: palette.surfaceAlt,
    borderRadius: 2,
    overflow: "hidden",
  },
  progressFill: { height: "100%", backgroundColor: palette.accent },
  tips: {
    marginTop: spacing(4),
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    gap: spacing(1),
  },
  tipTitle: { color: palette.text, fontWeight: "600", marginBottom: spacing(2) },
  tip: { color: palette.textMuted, fontSize: 13 },
  grid: {
    marginTop: spacing(5),
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing(3),
  },
  cell: {
    width: "47%",
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
  },
  cellFilled: { borderColor: palette.accent },
  thumb: { width: "100%", aspectRatio: 3 / 4 },
  empty: {
    width: "100%",
    aspectRatio: 3 / 4,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.background,
  },
  label: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing(3),
  },
  labelTitle: { color: palette.text, fontWeight: "600", fontSize: 14 },
  statusText: {
    color: palette.textMuted,
    marginTop: spacing(4),
    textAlign: "center",
  },
  doneButton: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    marginTop: spacing(6),
    alignItems: "center",
  },
  doneText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
});
