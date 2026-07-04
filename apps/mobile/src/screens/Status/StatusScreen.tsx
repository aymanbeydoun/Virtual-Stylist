import { LinearGradient } from "expo-linear-gradient";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useGamification } from "@/state/gamification";
import { LEVELS, levelForDays, nextLevel } from "@/theme/levels";
import { palette, radii, spacing } from "@/theme";

export function StatusScreen() {
  const daysUsed = useGamification((s) => s.daysUsed);
  const current = levelForDays(daysUsed);
  const upcoming = nextLevel(daysUsed);

  const daysToNext = upcoming ? upcoming.minDays - daysUsed : 0;
  const span = upcoming ? upcoming.minDays - current.minDays : 1;
  const progress = upcoming
    ? Math.min(1, Math.max(0, (daysUsed - current.minDays) / span))
    : 1;

  return (
    <SafeAreaView style={styles.root} edges={["bottom"]}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <View style={[styles.hero, { borderColor: current.color }]}>
          <View style={[styles.heroBadge, { backgroundColor: current.color }]}>
            <Text style={styles.heroEmoji}>{current.emoji}</Text>
          </View>
          <Text style={[styles.heroLevel, { color: current.color }]}>LEVEL {current.level}</Text>
          <Text style={styles.heroTitle}>{current.title}</Text>
          <Text style={styles.heroDays}>
            🔥 {daysUsed} {daysUsed === 1 ? "day" : "days"} styling with us
          </Text>

          <View style={styles.progressTrack}>
            <LinearGradient
              colors={[current.color, upcoming ? upcoming.color : current.color]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={[styles.progressFill, { width: `${progress * 100}%` }]}
            />
          </View>
          <Text style={styles.progressLabel}>
            {upcoming
              ? `${daysToNext} more ${daysToNext === 1 ? "day" : "days"} → ${upcoming.title}`
              : "You've reached the very top. Eternal Icon status! 🏆"}
          </Text>
        </View>

        <Text style={styles.sectionHeader}>Your style journey</Text>

        <View style={styles.ladder}>
          <View style={styles.headerRow}>
            <Text style={[styles.colLevel, styles.headerText]}>Level</Text>
            <Text style={[styles.colTime, styles.headerText]}>Time</Text>
            <Text style={[styles.colTitle, styles.headerText]}>Title</Text>
          </View>

          {LEVELS.map((lvl) => {
            const reached = daysUsed >= lvl.minDays;
            const isCurrent = lvl.level === current.level;
            return (
              <View
                key={lvl.level}
                style={[
                  styles.row,
                  isCurrent && { backgroundColor: `${lvl.color}22`, borderColor: lvl.color },
                ]}
              >
                <View style={styles.colLevel}>
                  <View
                    style={[
                      styles.levelDot,
                      { backgroundColor: lvl.color },
                      !reached && styles.levelDotLocked,
                    ]}
                  >
                    <Text style={styles.levelDotText}>{lvl.level}</Text>
                  </View>
                </View>
                <Text style={[styles.colTime, styles.cellMuted]}>{lvl.timeReached}</Text>
                <View style={styles.colTitle}>
                  <Text
                    style={[styles.cellTitle, { color: lvl.color }, !reached && styles.cellLocked]}
                  >
                    {lvl.emoji} {lvl.title}
                  </Text>
                  {isCurrent && <Text style={styles.youAreHere}>You are here</Text>}
                </View>
                <Text style={styles.lock}>{reached ? "✓" : "🔒"}</Text>
              </View>
            );
          })}
        </View>

        <Text style={styles.footnote}>
          Open STaiLE ME on new days to keep your streak climbing. Every level
          unlocks a fresh colour and title.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  hero: {
    alignItems: "center",
    borderWidth: 1.5,
    borderRadius: radii.lg,
    padding: spacing(5),
    backgroundColor: palette.surface,
  },
  heroBadge: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  heroEmoji: { fontSize: 30 },
  heroLevel: { fontWeight: "800", letterSpacing: 1, marginTop: spacing(3), fontSize: 12 },
  heroTitle: { color: palette.text, fontSize: 26, fontWeight: "800", marginTop: 2 },
  heroDays: { color: palette.textMuted, marginTop: spacing(2) },
  progressTrack: {
    width: "100%",
    height: 8,
    borderRadius: radii.pill,
    backgroundColor: palette.surfaceAlt,
    marginTop: spacing(4),
    overflow: "hidden",
  },
  progressFill: { height: "100%", borderRadius: radii.pill },
  progressLabel: { color: palette.textMuted, fontSize: 12, marginTop: spacing(2) },
  sectionHeader: {
    color: palette.text,
    fontSize: 16,
    fontWeight: "700",
    marginTop: spacing(7),
    marginBottom: spacing(3),
  },
  ladder: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: spacing(2),
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(2),
  },
  headerText: {
    color: palette.textMuted,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    fontWeight: "700",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(2.5),
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "transparent",
  },
  colLevel: { width: 48 },
  colTime: { width: 78 },
  colTitle: { flex: 1 },
  levelDot: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  levelDotLocked: { opacity: 0.5 },
  levelDotText: { color: palette.background, fontWeight: "800", fontSize: 13 },
  cellMuted: { color: palette.textMuted, fontSize: 13 },
  cellTitle: { fontWeight: "600", fontSize: 14 },
  cellLocked: { opacity: 0.7 },
  youAreHere: { color: palette.textMuted, fontSize: 10, marginTop: 1 },
  lock: { width: 22, textAlign: "right", fontSize: 13, color: palette.textMuted },
  footnote: {
    color: palette.textMuted,
    fontSize: 12,
    marginTop: spacing(5),
    lineHeight: 18,
  },
});
