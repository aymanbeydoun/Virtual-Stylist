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
  const words = text.split(" ");
  const count = [...text].length;

  useEffect(() => {
    kick.value = 0;
    kick.value = withTiming(1, { duration: 420, easing: Easing.out(Easing.cubic) });
  }, [trigger, text, kick]);

  // Letters are grouped per word so lines only wrap at word boundaries —
  // never in the middle of a word.
  let letterIndex = 0;
  return (
    <View style={styles.row} accessibilityRole="header" accessibilityLabel={text}>
      {words.map((word, w) => {
        const letters = [...word];
        const startIndex = letterIndex;
        letterIndex += letters.length + 1; // +1 keeps the stagger flowing across spaces
        return (
          <View key={`${w}-${word}`} style={styles.word}>
            {letters.map((c, i) => (
              <Letter
                key={`${startIndex + i}-${c}`}
                char={c}
                index={startIndex + i}
                count={count}
                kick={kick}
                style={style}
              />
            ))}
            {w < words.length - 1 && <Animated.Text style={style}> </Animated.Text>}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap" },
  word: { flexDirection: "row" },
});
