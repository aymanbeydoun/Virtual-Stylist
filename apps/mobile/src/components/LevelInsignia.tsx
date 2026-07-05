import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";

import { fonts } from "@/theme";

/**
 * Bespoke geometric insignias for the 16 progression ranks — trademark-grade
 * badge vectors, like a fashion house's seal. The silhouette sharpens as you
 * climb, and each rank carries its own inner mark (crosshair, seal ring,
 * notch bars, orbit points) so every level is a unique collectible:
 *
 *   1–4   Shard    (angular shield — the grind begins)
 *   5–8   Diamond  (cut and confident)
 *   9–12  Hex      (locked-in professional plate)
 *   13–15 Star     (four-point flare)
 *   16    Crown    (Eternal Icon)
 *
 * Reached ranks render filled with the rank colour; locked ranks render as a
 * dimmed outline so the ladder reads as a collectible set.
 */
function shapeFor(level: number): string {
  if (level >= 16) return "M6 36 L6 15 L16 25 L24 7 L32 25 L42 15 L42 36 Z";
  if (level >= 13) return "M24 2 L30 18 L46 24 L30 30 L24 46 L18 30 L2 24 L18 18 Z";
  if (level >= 9) return "M24 3 L42 13.5 L42 34.5 L24 45 L6 34.5 L6 13.5 Z";
  if (level >= 5) return "M24 4 L44 24 L24 44 L4 24 Z";
  return "M24 3 L42 12 L38 40 L24 45 L10 40 L6 12 Z";
}

/** Per-rank inner trademark mark — varies within each silhouette band. */
function InnerMark({ level, tone }: { level: number; tone: string }) {
  const common = { stroke: tone, strokeWidth: 1.4, fill: "none" as const };
  switch (level % 4) {
    case 1: // seal ring
      return <Circle cx={24} cy={24} r={12} {...common} />;
    case 2: // brutalist crosshair
      return (
        <Path d="M24 10 V16 M24 32 V38 M10 24 H16 M32 24 H38" {...common} strokeWidth={1.6} />
      );
    case 3: // twin notch bars
      return <Path d="M17 13 H31 M17 35 H31" {...common} strokeWidth={1.8} />;
    default: // orbit points
      return (
        <>
          <Circle cx={12.5} cy={24} r={1.8} fill={tone} />
          <Circle cx={35.5} cy={24} r={1.8} fill={tone} />
        </>
      );
  }
}

export function LevelInsignia({
  level,
  color,
  size = 34,
  reached = true,
  showNumber = true,
}: {
  level: number;
  color: string;
  size?: number;
  reached?: boolean;
  showNumber?: boolean;
}) {
  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size} viewBox="0 0 48 48">
        <Path
          d={shapeFor(level)}
          fill={reached ? color : "transparent"}
          stroke={reached ? "rgba(255,255,255,0.25)" : color}
          strokeOpacity={reached ? 1 : 0.55}
          strokeWidth={reached ? 1 : 1.5}
          strokeLinejoin="round"
        />
        <InnerMark
          level={level}
          tone={reached ? "rgba(10,11,14,0.4)" : `${color}55`}
        />
      </Svg>
      {showNumber && (
        <View style={StyleSheet.absoluteFill}>
          <View style={styles.center}>
            <Text
              style={[
                styles.number,
                {
                  fontSize: size * 0.32,
                  color: reached ? "#0A0B0E" : color,
                  opacity: reached ? 1 : 0.75,
                  // The crown's mass sits low; nudge the numeral to match.
                  marginTop: level >= 16 ? size * 0.12 : 0,
                },
              ]}
            >
              {level}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  number: { fontFamily: fonts.bodyBold, letterSpacing: -0.5 },
});
