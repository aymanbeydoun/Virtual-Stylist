import { LinearGradient } from "expo-linear-gradient";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CheckIcon, FlameIcon, LockIcon } from "@/components/icons";
import { LevelInsignia } from "@/components/LevelInsignia";
import { useGamification } from "@/state/gamification";
import { LEVELS, levelForDays, nextLevel } from "@/theme/levels";
import { fonts, glass, palette, radii, spacing } from "@/theme";

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
        {/* Milestone hero */}
        <View style={styles.hero}>
          <LevelInsignia level={current.level} color={current.color} size={72} />
          <Text style={[styles.heroLevel, { color: current.color }]}>
            LEVEL {String(current.level).padStart(2, "0")}
          </Text>
          <Text style={styles.heroTitle}>{current.title}</Text>
          <View style={styles.streakRow}>
            <FlameIcon size={15} color={current.color} />
            <Text style={styles.heroDays}>
              {daysUsed} {daysUsed === 1 ? "DAY" : "DAYS"} STYLING WITH US
            </Text>
          </View>

          {/* High-density sharp tracking bar */}
          <View style={styles.progressTrack}>
            <LinearGradient
              colors={[current.color, upcoming ? upcoming.color : current.color]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={[styles.progressFill, { width: `${progress * 100}%` }]}
            />
            <View style={styles.progressTicks} pointerEvents="none">
              {Array.from({ length: 9 }, (_, i) => (
                <View key={i} style={styles.tick} />
              ))}
            </View>
          </View>
          <Text style={styles.progressLabel}>
            {upcoming
              ? `${daysToNext} more ${daysToNext === 1 ? "day" : "days"} → ${upcoming.title}`
              : "You've reached the very top. Eternal Icon status."}
          </Text>
        </View>

        <Text style={styles.sectionHeader}>YOUR STYLE JOURNEY</Text>

        <View style={styles.ladder}>
          <View style={styles.headerRow}>
            <Text style={[styles.colLevel, styles.headerText]}>Rank</Text>
            <Text style={[styles.colTime, styles.headerText]}>Time</Text>
            <Text style={[styles.colTitle, styles.headerText]}>Title</Text>
          </View>

          {LEVELS.map((lvl, idx) => {
            const reached = daysUsed >= lvl.minDays;
            const isCurrent = lvl.level === current.level;
            return (
              <View
                key={lvl.level}
                style={[
                  styles.row,
                  idx > 0 && styles.rowDivider,
                  isCurrent && { backgroundColor: `${lvl.color}14`, borderColor: `${lvl.color}66` },
                ]}
              >
                <View style={styles.colLevel}>
                  <LevelInsignia level={lvl.level} color={lvl.color} size={32} reached={reached} />
                </View>
                <Text style={[styles.colTime, styles.cellMuted]}>{lvl.timeReached}</Text>
                <View style={styles.colTitle}>
                  <Text
                    style={[styles.cellTitle, { color: lvl.color }, !reached && styles.cellLocked]}
                  >
                    {lvl.title}
                  </Text>
                  {isCurrent && <Text style={styles.youAreHere}>YOU ARE HERE</Text>}
                </View>
                <View style={styles.lockCell}>
                  {reached ? (
                    <CheckIcon size={14} color={lvl.color} />
                  ) : (
                    <LockIcon size={13} color={palette.textMuted} />
                  )}
                </View>
              </View>
            );
          })}
        </View>

        <Text style={styles.footnote}>
          Open STaiLE ME on new days to keep your streak climbing. Every level
          unlocks a fresh colour and insignia.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  hero: {
    ...glass,
    alignItems: "center",
    borderRadius: radii.lg,
    padding: spacing(6),
  },
  heroLevel: {
    fontFamily: fonts.mono,
    letterSpacing: 3,
    marginTop: spacing(4),
    fontSize: 11,
  },
  heroTitle: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 26,
    marginTop: spacing(1),
    letterSpacing: 0.5,
    textAlign: "center",
  },
  streakRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1.5),
    marginTop: spacing(3),
  },
  heroDays: { color: palette.textMuted, fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5 },
  progressTrack: {
    width: "100%",
    height: 6,
    borderRadius: 2,
    backgroundColor: palette.surfaceAlt,
    marginTop: spacing(5),
    overflow: "hidden",
  },
  progressFill: { height: "100%", borderRadius: 2 },
  progressTicks: {
    ...StyleSheet.absoluteFillObject,
    flexDirection: "row",
    justifyContent: "space-evenly",
  },
  tick: { width: 1, height: "100%", backgroundColor: "rgba(10,11,14,0.5)" },
  progressLabel: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 0.5,
    marginTop: spacing(2.5),
  },
  sectionHeader: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 2.5,
    marginTop: spacing(7),
    marginBottom: spacing(3),
  },
  ladder: {
    ...glass,
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
    fontFamily: fonts.mono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 1.5,
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
  rowDivider: { borderTopWidth: 0 },
  colLevel: { width: 48 },
  colTime: { width: 78 },
  colTitle: { flex: 1 },
  cellMuted: { color: palette.textMuted, fontFamily: fonts.mono, fontSize: 12 },
  cellTitle: { fontFamily: fonts.bodyBold, fontSize: 14, letterSpacing: 0.2 },
  cellLocked: { opacity: 0.55 },
  youAreHere: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 8.5,
    letterSpacing: 1.5,
    marginTop: 2,
  },
  lockCell: { width: 24, alignItems: "flex-end" },
  footnote: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    fontSize: 12,
    marginTop: spacing(5),
    lineHeight: 18,
  },
});
