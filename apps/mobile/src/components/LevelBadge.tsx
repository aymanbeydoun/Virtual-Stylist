import { Pressable, StyleSheet, Text, View } from "react-native";

import { useGamification } from "@/state/gamification";
import { levelForDays } from "@/theme/levels";
import { palette, radii, spacing } from "@/theme";

/**
 * Compact status pill (shown top-right on the Style screen). Tapping it opens
 * the full status ladder.
 */
export function LevelBadge({ onPress }: { onPress: () => void }) {
  const daysUsed = useGamification((s) => s.daysUsed);
  const level = levelForDays(daysUsed);

  return (
    <Pressable
      onPress={onPress}
      style={[styles.badge, { borderColor: level.color }]}
      accessibilityRole="button"
      accessibilityLabel={`Level ${level.level}, ${level.title}. Open status`}
    >
      <View style={[styles.dot, { backgroundColor: level.color }]}>
        <Text style={styles.emoji}>{level.emoji}</Text>
      </View>
      <View>
        <Text style={[styles.level, { color: level.color }]}>LVL {level.level}</Text>
        <Text style={styles.title} numberOfLines={1}>
          {level.title}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(2),
    borderWidth: 1.5,
    borderRadius: radii.pill,
    paddingVertical: spacing(1.5),
    paddingHorizontal: spacing(2.5),
    backgroundColor: palette.surface,
    maxWidth: 160,
  },
  dot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  emoji: { fontSize: 14 },
  level: { fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  title: { color: palette.text, fontSize: 12, fontWeight: "600" },
});
