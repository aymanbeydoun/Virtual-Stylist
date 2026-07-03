import { type DemoItem, demoItemsBySlot } from "@/data/demoCloset";

export interface DemoOutfit {
  id: string;
  items: DemoItem[];
  rationale: string;
  confidence: number;
}

/** Tiny deterministic hash so the same vibe+occasion is stable across taps. */
function hash(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) >>> 0;
  }
  return h;
}

function pick(items: DemoItem[], n: number): DemoItem | undefined {
  if (items.length === 0) return undefined;
  return items[n % items.length];
}

/**
 * Compose three complete outfits from the demo closet, tuned (loosely) to the
 * chosen vibe and occasion. Runs entirely on-device — this is the offline
 * stand-in for the real backend stylist.
 */
export function stailMe(vibeLabel: string, occasionLabel: string): DemoOutfit[] {
  const seed = hash(`${vibeLabel}|${occasionLabel}`);
  const tops = demoItemsBySlot("top");
  const bottoms = demoItemsBySlot("bottom");
  const dresses = demoItemsBySlot("dress");
  const outerwear = demoItemsBySlot("outerwear");
  const shoes = demoItemsBySlot("shoes");
  const accessories = demoItemsBySlot("accessory");

  const vibe = vibeLabel.toLowerCase();
  const occ = occasionLabel.toLowerCase();

  const outfits: DemoOutfit[] = [];

  // Outfit 1 — top + bottom + shoes + accessory
  {
    const top = pick(tops, seed);
    const bottom = pick(bottoms, seed + 1);
    const shoe = pick(shoes, seed + 2);
    const acc = pick(accessories, seed + 3);
    const items = [top, bottom, shoe, acc].filter(Boolean) as DemoItem[];
    outfits.push({
      id: "demo-outfit-1",
      items,
      rationale:
        `A ${vibe} pick for your ${occ}. The ${top?.name.toLowerCase()} keeps it ` +
        `relaxed, and the ${shoe?.name.toLowerCase()} tie the whole look together.`,
      confidence: 0.88,
    });
  }

  // Outfit 2 — top + bottom + outerwear + shoes
  {
    const top = pick(tops, seed + 4);
    const bottom = pick(bottoms, seed + 5);
    const outer = pick(outerwear, seed + 6);
    const shoe = pick(shoes, seed + 7);
    const items = [top, bottom, outer, shoe].filter(Boolean) as DemoItem[];
    outfits.push({
      id: "demo-outfit-2",
      items,
      rationale:
        `Layered and ${vibe}: the ${outer?.name.toLowerCase()} adds an edge over the ` +
        `${top?.name.toLowerCase()} — perfect if your ${occ} runs cool.`,
      confidence: 0.82,
    });
  }

  // Outfit 3 — dress + shoes + accessory
  {
    const dress = pick(dresses, seed + 8);
    const shoe = pick(shoes, seed + 9);
    const acc = pick(accessories, seed + 10);
    const items = [dress, shoe, acc].filter(Boolean) as DemoItem[];
    outfits.push({
      id: "demo-outfit-3",
      items,
      rationale:
        `Want to keep it effortless? The ${dress?.name.toLowerCase()} does the work, ` +
        `finished with the ${shoe?.name.toLowerCase()} for a ${vibe} ${occ} vibe.`,
      confidence: 0.79,
    });
  }

  return outfits;
}
