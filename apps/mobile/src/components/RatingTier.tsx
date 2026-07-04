import { Pressable, StyleSheet, Text, View } from "react-native";

import { RATINGS } from "@/data/ratings";
import { fonts, palette, spacing } from "@/theme";

/**
 * Geometric feedback tiering — replaces the emoji reaction row. Six sharp
 * diamond segments; tapping tier N fills segments 1…N in the accent colour,
 * and the tier's name renders beneath in tracked mono caps.
 */
export function RatingTier({
  value,
  accent,
  onChange,
}: {
  value: number | null;
  accent: string;
  onChange: (v: number) => void;
}) {
  const selected = value ? RATINGS.find((r) => r.value === value) : null;

  return (
    <View>
      <View style={styles.row}>
        {RATINGS.map((r) => {
          const filled = value !== null && r.value <= value;
          return (
            <Pressable
              key={r.value}
              onPress={() => onChange(r.value)}
              style={styles.segmentHit}
              accessibilityRole="button"
              accessibilityLabel={`Rate ${r.label}`}
            >
              <View
                style={[
                  styles.diamond,
                  filled
                    ? { backgroundColor: accent, borderColor: accent }
                    : { borderColor: palette.hairline },
                ]}
              />
            </Pressable>
          );
        })}
      </View>
      <Text style={[styles.label, selected && { color: accent }]}>
        {selected ? selected.label.toUpperCase() : "RATE THE LOOK"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  segmentHit: {
    flex: 1,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  diamond: {
    width: 15,
    height: 15,
    borderWidth: 1.5,
    borderRadius: 2,
    transform: [{ rotate: "45deg" }],
    backgroundColor: "transparent",
  },
  label: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 2,
    textAlign: "center",
    marginTop: spacing(1.5),
  },
});
