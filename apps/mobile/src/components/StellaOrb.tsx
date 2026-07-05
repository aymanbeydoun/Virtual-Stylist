import { useEffect } from "react";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import Svg, { Circle, Defs, RadialGradient, Stop } from "react-native-svg";

/**
 * Stella's visual intelligence indicator — a fluid vector orb.
 *
 * Idle: a still, softly-lit sphere. Thinking: the orb breathes with a
 * chroma-shifting shimmer (two counter-pulsing gradient shells) instead of a
 * generic spinner.
 */
export function StellaOrb({
  size = 28,
  color,
  shiftColor,
  thinking = false,
}: {
  size?: number;
  color: string;
  /** Second hue for the chroma shift; defaults to white-hot. */
  shiftColor?: string;
  thinking?: boolean;
}) {
  const pulse = useSharedValue(0);

  useEffect(() => {
    if (thinking) {
      pulse.value = withRepeat(
        withTiming(1, { duration: 1100, easing: Easing.inOut(Easing.sin) }),
        -1,
        true,
      );
    } else {
      pulse.value = withTiming(0, { duration: 350 });
    }
  }, [thinking, pulse]);

  const coreStyle = useAnimatedStyle(() => ({
    transform: [{ scale: 1 + pulse.value * 0.14 }],
  }));
  const shellStyle = useAnimatedStyle(() => ({
    opacity: 1 - pulse.value,
    transform: [{ scale: 1 + pulse.value * 0.3 }],
  }));

  const shift = shiftColor ?? "#F5F6F7";

  return (
    <Animated.View style={[{ width: size, height: size }, coreStyle]}>
      {/* Chroma-shift shell — fades out as the core swells */}
      <Animated.View
        style={[
          { position: "absolute", left: 0, top: 0, width: size, height: size },
          shellStyle,
        ]}
      >
        <Svg width={size} height={size} viewBox="0 0 48 48">
          <Defs>
            <RadialGradient id="orbShift" cx="38%" cy="32%" r="75%">
              <Stop offset="0%" stopColor={shift} stopOpacity={0.9} />
              <Stop offset="55%" stopColor={color} stopOpacity={0.55} />
              <Stop offset="100%" stopColor={color} stopOpacity={0} />
            </RadialGradient>
          </Defs>
          <Circle cx={24} cy={24} r={23} fill="url(#orbShift)" />
        </Svg>
      </Animated.View>

      {/* Core sphere */}
      <Svg width={size} height={size} viewBox="0 0 48 48">
        <Defs>
          <RadialGradient id="orbCore" cx="36%" cy="30%" r="80%">
            <Stop offset="0%" stopColor="#FFFFFF" stopOpacity={0.95} />
            <Stop offset="30%" stopColor={color} stopOpacity={0.95} />
            <Stop offset="100%" stopColor={color} stopOpacity={0.25} />
          </RadialGradient>
        </Defs>
        <Circle cx={24} cy={24} r={19} fill="url(#orbCore)" />
        <Circle
          cx={24}
          cy={24}
          r={21.5}
          fill="none"
          stroke={color}
          strokeOpacity={0.35}
          strokeWidth={1}
        />
      </Svg>
    </Animated.View>
  );
}
