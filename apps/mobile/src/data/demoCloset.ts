/**
 * A ready-made example wardrobe so anyone can open Staile Me and try it
 * instantly — no backend, no photographing real clothes. Each item is drawn as
 * a coloured tile with an emoji instead of a real photo.
 */
export type DemoSlot = "top" | "bottom" | "dress" | "outerwear" | "shoes" | "accessory";

export interface DemoItem {
  id: string;
  slot: DemoSlot;
  name: string;
  emoji: string;
  /** Tile background colour (roughly the garment colour). */
  color: string;
}

export const DEMO_CLOSET: DemoItem[] = [
  // Tops
  { id: "top-white-tee", slot: "top", name: "White Tee", emoji: "👕", color: "#F1F5F9" },
  { id: "top-black-tee", slot: "top", name: "Black Tee", emoji: "👕", color: "#1F2937" },
  { id: "top-striped", slot: "top", name: "Striped Shirt", emoji: "👔", color: "#60A5FA" },
  { id: "top-denim-shirt", slot: "top", name: "Denim Shirt", emoji: "👔", color: "#3B82F6" },
  { id: "top-hoodie", slot: "top", name: "Grey Hoodie", emoji: "🧥", color: "#6B7280" },

  // Bottoms
  { id: "bottom-blue-jeans", slot: "bottom", name: "Blue Jeans", emoji: "👖", color: "#2563EB" },
  { id: "bottom-black-jeans", slot: "bottom", name: "Black Jeans", emoji: "👖", color: "#111827" },
  { id: "bottom-chino-shorts", slot: "bottom", name: "Chino Shorts", emoji: "🩳", color: "#D6BCA0" },
  { id: "bottom-joggers", slot: "bottom", name: "Joggers", emoji: "👖", color: "#4B5563" },

  // Dresses
  { id: "dress-summer", slot: "dress", name: "Summer Dress", emoji: "👗", color: "#F472B6" },
  { id: "dress-black", slot: "dress", name: "Black Dress", emoji: "👗", color: "#1F2937" },

  // Outerwear
  { id: "outer-denim-jacket", slot: "outerwear", name: "Denim Jacket", emoji: "🧥", color: "#1D4ED8" },
  { id: "outer-blazer", slot: "outerwear", name: "Navy Blazer", emoji: "🧥", color: "#374151" },

  // Shoes
  { id: "shoes-white-sneakers", slot: "shoes", name: "White Sneakers", emoji: "👟", color: "#F3F4F6" },
  { id: "shoes-black-boots", slot: "shoes", name: "Black Boots", emoji: "🥾", color: "#1F2937" },
  { id: "shoes-sandals", slot: "shoes", name: "Sandals", emoji: "🩴", color: "#F59E0B" },
  { id: "shoes-heels", slot: "shoes", name: "Red Heels", emoji: "👠", color: "#EF4444" },

  // Accessories
  { id: "acc-cap", slot: "accessory", name: "Red Cap", emoji: "🧢", color: "#DC2626" },
  { id: "acc-sunglasses", slot: "accessory", name: "Sunglasses", emoji: "🕶️", color: "#111827" },
  { id: "acc-watch", slot: "accessory", name: "Watch", emoji: "⌚", color: "#6B7280" },
  { id: "acc-tote", slot: "accessory", name: "Tote Bag", emoji: "👜", color: "#A16207" },
];

export function demoItemsBySlot(slot: DemoSlot): DemoItem[] {
  return DEMO_CLOSET.filter((i) => i.slot === slot);
}
