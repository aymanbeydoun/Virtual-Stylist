import { useEffect } from "react";
import { StyleSheet, View, type TextStyle } from "react-native";
import Animated, {
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
  type SharedValue,
} from "react-native-reanimated";

/**
 * Kinetic brutalist headline — on every `trigger` change the letters snap
 * back into alignment with sharp, staggered, click-like motion (drop-style
 * typography, not a soft fade).
 */
function Letter({
  char,
  index,
  count,
  kick,
  style,
}: {
  char: string;
  index: number;
  count: number;
  kick: SharedValue<number>;
  style?: TextStyle;
}) {
  const animatedStyle = useAnimatedStyle(() => {
    // Each letter owns a slice of the master timeline — a hard stagger.
    const start = index / (count + 3);
    const end = start + 3 / (count + 3);
    const p = interpolate(kick.value, [start, end], [0, 1], "clamp");
    return {
      opacity: 0.15 + p * 0.85,
      transform: [{ translateY: (1 - p) * 9 }, { scaleY: 0.7 + p * 0.3 }],
    };
  });
  return (
    <Animated.Text style={[style, animatedStyle]}>
      {char === " " ? " " : char}
    </Animated.Text>
  );
}

export function KineticTitle({
  text,
  trigger,
  style,
}: {
  text: string;
  /** Any changing value — each change re-fires the snap animation. */
  trigger: string | number;
  style?: TextStyle;
}) {
  const kick = useSharedValue(1);
  const chars = [...text];

  useEffect(() => {
    kick.value = 0;
    kick.value = withTiming(1, { duration: 420, easing: Easing.out(Easing.cubic) });
  }, [trigger, text, kick]);

  return (
    <View style={styles.row} accessibilityRole="header" accessibilityLabel={text}>
      {chars.map((c, i) => (
        <Letter key={`${i}-${c}`} char={c} index={i} count={chars.length} kick={kick} style={style} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap" },
});
