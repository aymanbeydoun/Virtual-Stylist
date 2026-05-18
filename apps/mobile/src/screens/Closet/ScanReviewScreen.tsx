import { Ionicons } from "@expo/vector-icons";
import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
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

import { wardrobeApi } from "@/api/wardrobe";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Review screen for SAM 2 multi-garment detections.
 *
 * Reached from AddItemScreen after the user taps "Scan for multiple items"
 * and the backend returns N preview cutouts. Renders each as a thumbnail
 * with a checkbox; the user confirms which to add to the closet.
 *
 * Adds N items in a single bulk call. The standard ingest pipeline still
 * runs per item afterward (preflight + classifier + bg-removal + tagging).
 */
export function ScanReviewScreen() {
  const route =
    useRoute<RouteProp<RootStackParamList, "ScanReview">>();
  const nav = useNavigation<Nav>();
  const qc = useQueryClient();
  const profile = useActiveProfile();
  const { regions } = route.params;

  // Default: everything selected. The user de-selects what they don't want.
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(regions.map((r) => r.preview_key)),
  );

  const toggle = (key: string) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const commit = useMutation({
    mutationFn: async () => {
      const keys = Array.from(selected);
      if (keys.length === 0) throw new Error("Select at least one item.");
      const owner = {
        kind: profile.ownerKind,
        id: profile.ownerId ?? undefined,
      };
      return wardrobeApi.createBulk(keys, owner);
    },
    onSuccess: async (created) => {
      await qc.invalidateQueries({ queryKey: ["wardrobe"] });
      Alert.alert(
        "Added to your closet",
        `${created.length} item${created.length === 1 ? "" : "s"} now tagging in the background.`,
      );
      // Pop back to the closet (twice — once past ScanReview, once past AddItem).
      nav.pop(2);
    },
    onError: (e) =>
      Alert.alert(
        "Couldn't add items",
        e instanceof Error ? e.message : "Try again.",
      ),
  });

  if (regions.length === 0) {
    return (
      <View style={styles.emptyRoot}>
        <Ionicons
          name="scan-outline"
          size={42}
          color={palette.textMuted}
        />
        <Text style={styles.emptyTitle}>No separate items found</Text>
        <Text style={styles.emptyHint}>
          The scanner couldn&apos;t pick apart distinct garments in this photo.
          Try cropping in tighter, or add the photo as one item instead.
        </Text>
        <Pressable style={styles.primary} onPress={() => nav.goBack()}>
          <Text style={styles.primaryText}>Back</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>
          We see {regions.length} item{regions.length === 1 ? "" : "s"}
        </Text>
        <Text style={styles.subtitle}>
          Tap to deselect any that aren&apos;t clothing.
        </Text>
        <View style={styles.grid}>
          {regions.map((r) => {
            const isOn = selected.has(r.preview_key);
            return (
              <Pressable
                key={r.preview_key}
                style={[styles.cell, isOn && styles.cellActive]}
                onPress={() => toggle(r.preview_key)}
              >
                <Image
                  source={{
                    uri: `${baseUrl}/api/v1/wardrobe/_local_read/${r.preview_key}`,
                  }}
                  style={styles.thumb}
                  contentFit="contain"
                />
                <View
                  style={[
                    styles.check,
                    isOn ? styles.checkOn : styles.checkOff,
                  ]}
                >
                  <Ionicons
                    name={isOn ? "checkmark" : "add"}
                    size={16}
                    color={isOn ? palette.onAccent : palette.text}
                  />
                </View>
              </Pressable>
            );
          })}
        </View>
      </ScrollView>
      <View style={styles.footer}>
        <Pressable
          style={[styles.primary, commit.isPending && styles.primaryDisabled]}
          onPress={() => commit.mutate()}
          disabled={commit.isPending || selected.size === 0}
        >
          {commit.isPending ? (
            <ActivityIndicator color={palette.onAccent} />
          ) : (
            <Text style={styles.primaryText}>
              Add {selected.size} to closet
            </Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  scroll: { padding: spacing(5), paddingBottom: spacing(10) },
  title: {
    color: palette.text,
    fontSize: 24,
    fontWeight: "700",
    marginBottom: spacing(1),
  },
  subtitle: {
    color: palette.textMuted,
    marginBottom: spacing(5),
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing(3),
  },
  cell: {
    width: "47%",
    aspectRatio: 1,
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    overflow: "hidden",
    borderWidth: 2,
    borderColor: "transparent",
    padding: spacing(2),
  },
  cellActive: { borderColor: palette.accent },
  thumb: { width: "100%", height: "100%" },
  check: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  checkOn: { backgroundColor: palette.accent },
  checkOff: { backgroundColor: palette.surfaceAlt },
  footer: {
    padding: spacing(5),
    borderTopColor: palette.surfaceAlt,
    borderTopWidth: 1,
    backgroundColor: palette.background,
  },
  primary: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryDisabled: { opacity: 0.5 },
  primaryText: {
    color: palette.onAccent,
    fontWeight: "700",
    fontSize: 16,
  },
  emptyRoot: {
    flex: 1,
    backgroundColor: palette.background,
    padding: spacing(8),
    alignItems: "center",
    justifyContent: "center",
    gap: spacing(3),
  },
  emptyTitle: { color: palette.text, fontSize: 20, fontWeight: "700" },
  emptyHint: {
    color: palette.textMuted,
    textAlign: "center",
    lineHeight: 20,
  },
});
