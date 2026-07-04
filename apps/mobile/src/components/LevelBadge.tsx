import { Pressable, StyleSheet, Text, View } from "react-native";

import { LevelInsignia } from "@/components/LevelInsignia";
import { useGamification } from "@/state/gamification";
import { levelForDays } from "@/theme/levels";
import { fonts, glass, palette, radii, spacing } from "@/theme";

/**
 * Compact status pill (shown top-right on the Style screen). Tapping it opens
 * the full status ladder. Glass surface + geometric rank insignia.
 */
export function LevelBadge({ onPress }: { onPress: () => void }) {
  const daysUsed = useGamification((s) => s.daysUsed);
  const level = levelForDays(daysUsed);

  return (
    <Pressable
      onPress={onPress}
      style={styles.badge}
      accessibilityRole="button"
      accessibilityLabel={`Level ${level.level}, ${level.title}. Open status`}
    >
      <LevelInsignia level={level.level} color={level.color} size={30} />
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
    ...glass,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(2),
    borderRadius: radii.pill,
    paddingVertical: spacing(1.5),
    paddingHorizontal: spacing(3),
    maxWidth: 168,
  },
  level: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.5 },
  title: { color: palette.text, fontFamily: fonts.bodyBold, fontSize: 12 },
});
