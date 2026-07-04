import type { GarmentKind } from "@/components/GarmentIcon";

/**
 * A ready-made example wardrobe so anyone can open STaiLE ME and try it
 * instantly — no backend, no photographing real clothes. Each item renders as
 * a flat vector garment illustration (see GarmentIcon) on a muted off-black
 * backdrop — no emoji tiles.
 */
export type DemoSlot = "top" | "bottom" | "dress" | "outerwear" | "shoes" | "accessory";

export interface DemoItem {
  id: string;
  slot: DemoSlot;
  name: string;
  /** Which vector illustration to draw. */
  icon: GarmentKind;
  /** The garment's own colour (fills the illustration, not the tile). */
  color: string;
}

export const DEMO_CLOSET: DemoItem[] = [
  // Tops
  { id: "top-white-tee", slot: "top", name: "White Tee", icon: "tee", color: "#F1F5F9" },
  { id: "top-black-tee", slot: "top", name: "Black Tee", icon: "tee", color: "#1F2937" },
  { id: "top-striped", slot: "top", name: "Striped Shirt", icon: "stripedTee", color: "#60A5FA" },
  { id: "top-denim-shirt", slot: "top", name: "Denim Shirt", icon: "shirt", color: "#3B82F6" },
  { id: "top-hoodie", slot: "top", name: "Grey Hoodie", icon: "hoodie", color: "#6B7280" },

  // Bottoms
  { id: "bottom-blue-jeans", slot: "bottom", name: "Blue Jeans", icon: "jeans", color: "#2563EB" },
  { id: "bottom-black-jeans", slot: "bottom", name: "Black Jeans", icon: "jeans", color: "#111827" },
  { id: "bottom-chino-shorts", slot: "bottom", name: "Chino Shorts", icon: "shorts", color: "#D6BCA0" },
  { id: "bottom-joggers", slot: "bottom", name: "Joggers", icon: "joggers", color: "#4B5563" },

  // Dresses
  { id: "dress-summer", slot: "dress", name: "Summer Dress", icon: "dress", color: "#F472B6" },
  { id: "dress-black", slot: "dress", name: "Black Dress", icon: "dress", color: "#1F2937" },

  // Outerwear
  { id: "outer-denim-jacket", slot: "outerwear", name: "Denim Jacket", icon: "jacket", color: "#1D4ED8" },
  { id: "outer-blazer", slot: "outerwear", name: "Navy Blazer", icon: "blazer", color: "#374151" },

  // Shoes
  { id: "shoes-white-sneakers", slot: "shoes", name: "White Sneakers", icon: "sneaker", color: "#F3F4F6" },
  { id: "shoes-black-boots", slot: "shoes", name: "Black Boots", icon: "boot", color: "#1F2937" },
  { id: "shoes-sandals", slot: "shoes", name: "Sandals", icon: "sandal", color: "#F59E0B" },
  { id: "shoes-heels", slot: "shoes", name: "Red Heels", icon: "heel", color: "#EF4444" },

  // Accessories
  { id: "acc-cap", slot: "accessory", name: "Red Cap", icon: "cap", color: "#DC2626" },
  { id: "acc-sunglasses", slot: "accessory", name: "Sunglasses", icon: "sunglasses", color: "#111827" },
  { id: "acc-watch", slot: "accessory", name: "Watch", icon: "watch", color: "#6B7280" },
  { id: "acc-tote", slot: "accessory", name: "Tote Bag", icon: "tote", color: "#A16207" },
];

export function demoItemsBySlot(slot: DemoSlot): DemoItem[] {
  return DEMO_CLOSET.filter((i) => i.slot === slot);
}
