import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { gapsApi } from "@/api/gaps";
import type { GapFinding } from "@/api/types";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

const SEVERITY_LABEL: Record<GapFinding["severity"], string> = {
  high: "Must-have",
  medium: "Worth adding",
  low: "Nice upgrade",
};

const SEVERITY_COLOR: Record<GapFinding["severity"], string> = {
  high: "#ff6b6b",
  medium: "#ffd166",
  low: "#a8dadc",
};

export function GapsScreen() {
  const profile = useActiveProfile();
  const qc = useQueryClient();
  const owner = { kind: profile.ownerKind, id: profile.ownerId ?? undefined };
  const queryKey = ["gaps", profile.ownerKind, profile.ownerId];

  const gaps = useQuery({
    queryKey,
    queryFn: () => gapsApi.list(owner, false),
  });

  const runAnalysis = useMutation({
    mutationFn: () => gapsApi.run(owner),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
    onError: (err) =>
      Alert.alert("Couldn't analyse", err instanceof Error ? err.message : "Try again later."),
  });

  const dismiss = useMutation({
    mutationFn: (gapId: string) => gapsApi.dismiss(gapId, owner),
    onMutate: async (gapId) => {
      await qc.cancelQueries({ queryKey });
      const prev = qc.getQueryData<GapFinding[]>(queryKey);
      qc.setQueryData<GapFinding[]>(queryKey, (old) => (old ?? []).filter((g) => g.id !== gapId));
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKey, ctx.prev);
    },
  });

  const data = gaps.data ?? [];

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.eyebrow}>Insights</Text>
          <Text style={styles.title}>Closet gaps</Text>
          <Text style={styles.subtitle}>
            The AI looks at your wardrobe holistically and finds outfits you can&apos;t yet build.
          </Text>
        </View>
      </View>

      <Pressable
        style={[styles.analyseButton, runAnalysis.isPending && styles.analyseButtonBusy]}
        onPress={() => runAnalysis.mutate()}
        disabled={runAnalysis.isPending}
      >
        {runAnalysis.isPending ? (
          <ActivityIndicator color={palette.onAccent} />
        ) : (
          <Text style={styles.analyseButtonText}>
            {data.length > 0 ? "Refresh analysis" : "Analyse my closet"}
          </Text>
        )}
      </Pressable>

      {gaps.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator color={palette.accent} />
        </View>
      ) : data.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>No gaps yet</Text>
          <Text style={styles.emptyText}>
            Tap &quot;Analyse my closet&quot; to see what would round out your wardrobe.
          </Text>
        </View>
      ) : (
        <FlatList
          data={data}
          keyExtractor={(g) => g.id}
          contentContainerStyle={{ padding: spacing(4), gap: spacing(3) }}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View
                  style={[styles.sevPill, { backgroundColor: SEVERITY_COLOR[item.severity] }]}
                >
                  <Text style={styles.sevText}>{SEVERITY_LABEL[item.severity]}</Text>
                </View>
                <Text style={styles.slot}>{item.slot.toUpperCase()}</Text>
              </View>
              <Text style={styles.cardTitle}>{item.title}</Text>
              {item.rationale && <Text style={styles.cardRationale}>{item.rationale}</Text>}
              <View style={styles.cardActions}>
                <Pressable
                  style={styles.actionGhost}
                  onPress={() => dismiss.mutate(item.id)}
                >
                  <Text style={styles.actionGhostText}>Not relevant</Text>
                </Pressable>
              </View>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  header: { padding: spacing(5), paddingBottom: spacing(3) },
  eyebrow: {
    color: palette.textMuted,
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  subtitle: { color: palette.textMuted, marginTop: spacing(2), lineHeight: 20 },
  analyseButton: {
    marginHorizontal: spacing(4),
    marginBottom: spacing(3),
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
  },
  analyseButtonBusy: { opacity: 0.6 },
  analyseButtonText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing(6) },
  emptyTitle: { color: palette.text, fontSize: 18, fontWeight: "600", marginBottom: spacing(2) },
  emptyText: { color: palette.textMuted, textAlign: "center", lineHeight: 20 },
  card: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    gap: spacing(2),
  },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: spacing(2) },
  sevPill: {
    paddingHorizontal: spacing(2),
    paddingVertical: 4,
    borderRadius: radii.pill,
  },
  sevText: { color: "#1a1a2e", fontSize: 11, fontWeight: "700" },
  slot: { color: palette.textMuted, fontSize: 11, letterSpacing: 1 },
  cardTitle: { color: palette.text, fontSize: 16, fontWeight: "600" },
  cardRationale: { color: palette.textMuted, lineHeight: 20 },
  cardActions: { flexDirection: "row", marginTop: spacing(2) },
  actionGhost: { paddingVertical: spacing(2), paddingHorizontal: spacing(3) },
  actionGhostText: { color: palette.textMuted, fontWeight: "600" },
});
