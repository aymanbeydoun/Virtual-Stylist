import { StyleSheet, View, type ViewStyle } from "react-native";

import { GarmentIcon } from "@/components/GarmentIcon";
import type { DemoItem, DemoSlot } from "@/data/demoCloset";

/**
 * Lookbook canvas — outfit pieces overlap organically (jacket layered over the
 * tee, bottoms tucked across the hem, shoes anchored beneath) so a look reads
 * as a curated fashion sketch, not an inventory grid of squares.
 *
 * Placements are percentage-based collage coordinates tuned for a card-width
 * canvas; rotation gives each piece a hand-placed feel.
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

export function OutfitCanvas({ items }: { items: DemoItem[] }) {
  const hasDress = items.some((i) => i.slot === "dress");
  const placements = hasDress ? DRESS : STANDARD;

  return (
    <View style={styles.canvas}>
      {items.map((item) => {
        const p = placements[item.slot];
        if (!p) return null;
        const style: ViewStyle = {
          position: "absolute",
          left: p.left,
          top: p.top,
          zIndex: p.zIndex,
          transform: [{ rotate: p.rotate }],
        };
        return (
          <View key={item.id} style={style}>
            <GarmentIcon kind={item.icon} color={item.color} size={p.size} />
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  canvas: {
    height: 196,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.06)",
    overflow: "hidden",
  },
});
