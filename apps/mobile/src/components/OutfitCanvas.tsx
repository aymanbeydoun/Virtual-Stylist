import { useRef } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";
import { Directions, Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import Svg, { Defs, Ellipse, RadialGradient, Stop } from "react-native-svg";

import { GarmentIcon } from "@/components/GarmentIcon";
import type { DemoItem, DemoSlot } from "@/data/demoCloset";
import { hapticRackTick } from "@/lib/haptics";

/**
 * The signature lookbook canvas — outfit pieces overlap organically with
 * realistic layer stacking, and every layer is alive:
 *
 * FLICK-TO-SWAP — swipe (or tap) a single garment layer to carousel through
 * the closet's alternatives for just that slot. The leaving piece slides out,
 * the newcomer snaps in on a spring, and the haptic engine ticks like a steel
 * clothing rack.
 *
 * Each garment floats over an asymmetric gallery shadow, as if lit by a
 * single overhead light.
 */
interface Placement {
  left: `${number}%`;
  top: number;
  size: number;
  rotate: string;
  zIndex: number;
}

const STANDARD: Partial<Record<DemoSlot, Placement>> = {
  top: { left: "14%", top: 4, size: 104, rotate: "-3deg", zIndex: 2 },
  outerwear: { left: "-1%", top: 34, size: 96, rotate: "-9deg", zIndex: 3 },
  bottom: { left: "50%", top: 16, size: 102, rotate: "5deg", zIndex: 2 },
  shoes: { left: "58%", top: 104, size: 82, rotate: "-6deg", zIndex: 1 },
  accessory: { left: "79%", top: 6, size: 52, rotate: "9deg", zIndex: 4 },
};

const DRESS: Partial<Record<DemoSlot, Placement>> = {
  dress: { left: "22%", top: 0, size: 128, rotate: "-2deg", zIndex: 2 },
  outerwear: { left: "0%", top: 30, size: 92, rotate: "-10deg", zIndex: 3 },
  shoes: { left: "58%", top: 100, size: 82, rotate: "6deg", zIndex: 1 },
  accessory: { left: "76%", top: 10, size: 52, rotate: "9deg", zIndex: 4 },
};

/** Asymmetric soft shadow — single overhead gallery light, slightly camera-left. */
export function GalleryShadow({ width }: { width: number }) {
  const h = Math.max(10, width * 0.18);
  return (
    <Svg width={width} height={h} viewBox="0 0 100 18">
      <Defs>
        <RadialGradient id="galleryShadow" cx="46%" cy="50%" rx="50%" ry="50%">
          <Stop offset="0%" stopColor="#000" stopOpacity={0.45} />
          <Stop offset="70%" stopColor="#000" stopOpacity={0.16} />
          <Stop offset="100%" stopColor="#000" stopOpacity={0} />
        </RadialGradient>
      </Defs>
      <Ellipse cx={54} cy={9} rx={44} ry={7.5} fill="url(#galleryShadow)" />
    </Svg>
  );
}

function GarmentLayer({
  item,
  placement,
  onSwap,
}: {
  item: DemoItem;
  placement: Placement;
  /** Ask the parent to replace this slot's item; dir is the flick direction. */
  onSwap: (slot: DemoSlot, dir: 1 | -1) => void;
}) {
  const offset = useSharedValue(0);
  const fade = useSharedValue(1);
  const busy = useRef(false);

  const startSwap = (dir: 1 | -1) => {
    if (busy.current) return;
    busy.current = true;
    hapticRackTick();

    // Slide the leaving piece out…
    offset.value = withTiming(-dir * 42, { duration: 110 });
    fade.value = withTiming(0, { duration: 110 });
    setTimeout(() => {
      // …commit the newcomer, then spring it in from the flick side.
      onSwap(item.slot, dir);
      offset.value = dir * 42;
      offset.value = withSpring(0, { damping: 15, stiffness: 260, mass: 0.7 });
      fade.value = withTiming(1, { duration: 170 });
      busy.current = false;
    }, 120);
  };

  const flingLeft = Gesture.Fling()
    .direction(Directions.LEFT)
    .runOnJS(true)
    .onEnd(() => startSwap(-1));
  const flingRight = Gesture.Fling()
    .direction(Directions.RIGHT)
    .runOnJS(true)
    .onEnd(() => startSwap(1));
  const tap = Gesture.Tap()
    .runOnJS(true)
    .onEnd(() => startSwap(1));
  const gesture = Gesture.Exclusive(flingLeft, flingRight, tap);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: fade.value,
    transform: [{ translateX: offset.value }],
  }));

  const wrapper: ViewStyle = {
    position: "absolute",
    left: placement.left,
    top: placement.top,
    zIndex: placement.zIndex,
  };

  return (
    <View style={wrapper}>
      <GestureDetector gesture={gesture}>
        <Animated.View
          style={animatedStyle}
          accessibilityRole="button"
          accessibilityLabel={`${item.name}. Flick or tap to swap this piece`}
        >
          <View style={{ transform: [{ rotate: placement.rotate }] }}>
            <GarmentIcon kind={item.icon} color={item.color} size={placement.size} />
          </View>
          <View style={styles.shadowSeat}>
            <GalleryShadow width={placement.size * 0.86} />
          </View>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

export function OutfitCanvas({
  items,
  onSwap,
}: {
  items: DemoItem[];
  onSwap: (slot: DemoSlot, dir: 1 | -1) => void;
}) {
  const hasDress = items.some((i) => i.slot === "dress");
  const placements = hasDress ? DRESS : STANDARD;

  return (
    <View style={styles.canvas}>
      {items.map((item) => {
        const p = placements[item.slot];
        if (!p) return null;
        return <GarmentLayer key={item.slot} item={item} placement={p} onSwap={onSwap} />;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  canvas: {
    height: 200,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.06)",
    overflow: "hidden",
  },
  shadowSeat: { alignItems: "center", marginTop: -6 },
});
