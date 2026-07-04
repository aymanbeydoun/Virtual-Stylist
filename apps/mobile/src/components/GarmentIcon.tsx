import Svg, { Circle, Path, Rect } from "react-native-svg";

/**
 * Flat vector garment illustrations — the closet's visual asset pipeline.
 *
 * Every garment renders as a clean silhouette filled with its item colour,
 * finished with a thin light outline (so ink-dark garments still read on the
 * off-black backdrops) and minimal detail strokes whose tone auto-adjusts to
 * the garment's luminance. No native emojis anywhere.
 */
export type GarmentKind =
  | "tee"
  | "stripedTee"
  | "shirt"
  | "hoodie"
  | "jeans"
  | "shorts"
  | "joggers"
  | "dress"
  | "jacket"
  | "blazer"
  | "sneaker"
  | "boot"
  | "sandal"
  | "heel"
  | "cap"
  | "sunglasses"
  | "watch"
  | "tote";

const OUTLINE = "rgba(255,255,255,0.38)";

/** Pick a detail-line tone that contrasts with the garment fill. */
function detailTone(hex: string): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return "rgba(255,255,255,0.5)";
  const v = parseInt(m[1]!, 16);
  const r = (v >> 16) & 255;
  const g = (v >> 8) & 255;
  const b = v & 255;
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 140 ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.5)";
}

export function GarmentIcon({
  kind,
  color,
  size = 64,
}: {
  kind: GarmentKind;
  color: string;
  size?: number;
}) {
  const detail = detailTone(color);
  const common = { fill: color, stroke: OUTLINE, strokeWidth: 1.5, strokeLinejoin: "round" as const };
  const line = { stroke: detail, strokeWidth: 1.6, strokeLinecap: "round" as const, fill: "none" };

  const TEE_BODY =
    "M22 10 L13 14 L5 23 L12 31 L17 27 L17 54 L47 54 L47 27 L52 31 L59 23 L51 14 L42 10 C40 14 36.5 16 32 16 C27.5 16 24 14 22 10 Z";

  switch (kind) {
    case "tee":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d={TEE_BODY} {...common} />
          <Path d="M24 11.5 C26 15.5 29 17.5 32 17.5 C35 17.5 38 15.5 40 11.5" {...line} />
        </Svg>
      );

    case "stripedTee":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d={TEE_BODY} {...common} />
          <Path d="M17 30 H47 M17 37 H47 M17 44 H47 M17 51 H47" {...line} strokeWidth={2.4} />
          <Path d="M24 11.5 C26 15.5 29 17.5 32 17.5 C35 17.5 38 15.5 40 11.5" {...line} />
        </Svg>
      );

    case "shirt":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d={TEE_BODY} {...common} />
          <Path d="M26 10.5 L32 19 L38 10.5" {...line} />
          <Path d="M32 19 V54" {...line} />
          <Circle cx={29.5} cy={28} r={1.1} fill={detail} />
          <Circle cx={29.5} cy={38} r={1.1} fill={detail} />
          <Circle cx={29.5} cy={48} r={1.1} fill={detail} />
        </Svg>
      );

    case "hoodie":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M22 13 L10 19 L7 42 L15 44 L17 32 L17 56 L47 56 L47 32 L49 44 L57 42 L54 19 L42 13 C40 17 36.5 19 32 19 C27.5 19 24 17 22 13 Z"
            {...common}
          />
          <Path d="M22 13 C22 5.5 42 5.5 42 13 C40 17 36.5 19 32 19 C27.5 19 24 17 22 13 Z" {...common} />
          <Path d="M29 20 L28 27 M35 20 L36 27" {...line} />
          <Path d="M24 44 H40 L38 54 H26 Z" {...line} />
        </Svg>
      );

    case "jeans":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d="M18 8 H46 V15 L44 56 H35 L32 28 L29 56 H20 L18 15 Z" {...common} />
          <Path d="M18 15 H46" {...line} />
          <Path d="M32 15 V22" {...line} />
          <Path d="M20 19 C23 21 25 21 27 19 M44 19 C41 21 39 21 37 19" {...line} />
        </Svg>
      );

    case "shorts":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d="M16 16 H48 V23 L50 46 H35 L32 30 L29 46 H14 L16 23 Z" {...common} />
          <Path d="M16 23 H48" {...line} />
          <Path d="M32 23 V29" {...line} />
        </Svg>
      );

    case "joggers":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d="M19 8 H45 V15 L42 50 H34.5 L32 28 L29.5 50 H22 Z" {...common} />
          <Rect x={33} y={50} width={10} height={6} rx={1.5} {...common} />
          <Rect x={21} y={50} width={10} height={6} rx={1.5} {...common} />
          <Path d="M28 12 L30 17 M36 12 L34 17" {...line} />
        </Svg>
      );

    case "dress":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M24 8 L27 8 C28 11 30 12.5 32 12.5 C34 12.5 36 11 37 8 L40 8 L38 26 L49 55 L15 55 L26 26 Z"
            {...common}
          />
          <Path d="M26.5 26 H37.5" {...line} />
          <Path d="M24 40 C29 43 35 43 40 40" {...line} />
        </Svg>
      );

    case "jacket":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M22 11 L9 17 L6 41 L14 43 L17 30 L17 56 L47 56 L47 30 L50 43 L58 41 L55 17 L42 11 L32 22 Z"
            {...common}
          />
          <Path d="M22 11 L32 22 L27 27 L23 16 Z M42 11 L32 22 L37 27 L41 16 Z" {...common} />
          <Path d="M32 24 V56" {...line} />
          <Path d="M17 46 H29 M35 46 H47" {...line} />
        </Svg>
      );

    case "blazer":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M23 9 L10 15 L8 44 L16 45 L17 30 L17 57 L47 57 L47 30 L48 45 L56 44 L54 15 L41 9 L32 34 Z"
            {...common}
          />
          <Path d="M23 9 L32 34 L26 24 L25 12 Z M41 9 L32 34 L38 24 L39 12 Z" {...common} />
          <Circle cx={32} cy={41} r={1.3} fill={detail} />
          <Path d="M20 50 H27 M37 50 H44" {...line} />
        </Svg>
      );

    case "sneaker":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M6 44 C6 38 12 36 18 32 C24 28 27 24 31 24 C34 24 35 28 43 32 C51 36 58 38 58 43 L58 47 H6 Z"
            {...common}
          />
          <Path d="M6 47 H58 V50 C40 52 24 52 6 50 Z" {...common} />
          <Path d="M28 30 L34 33 M25 34 L31 37 M22 38 L28 41" {...line} />
        </Svg>
      );

    case "boot":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M22 8 H40 V32 C48 34 54 39 56 45 L56 52 H22 Z"
            {...common}
          />
          <Path d="M22 52 H56 V56 H22 Z" {...common} />
          <Path d="M22 14 H40 M40 32 C44 33 47 34 50 37" {...line} />
        </Svg>
      );

    case "sandal":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d="M8 46 C22 41 42 41 56 46 L56 51 C42 47 22 47 8 51 Z" {...common} />
          <Path d="M18 46.5 C23 36 33 36 37 45" {...line} strokeWidth={2.2} />
          <Path d="M44 45 C47 41 51 41 53 45" {...line} strokeWidth={2.2} />
        </Svg>
      );

    case "heel":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path
            d="M7 47 C18 44 28 38 38 25 L45 29 C41 37 38 42 37 47 L37 49 L26 49 C19 50 12 50 7 49 Z"
            {...common}
          />
          <Path d="M43 33 L49 52 L44 52 L39 40" {...common} />
          <Path d="M12 47 C20 45 26 43 31 39" {...line} />
        </Svg>
      );

    case "cap":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d="M12 36 C12 20 48 20 48 36 L48 40 L12 40 Z" {...common} />
          <Path d="M46 36 C54 36 60 39 60 43 C52 41 48 40 46 40 Z" {...common} />
          <Path d="M30 21 V38" {...line} />
          <Circle cx={30} cy={19.5} r={1.6} fill={color} stroke={OUTLINE} strokeWidth={1.2} />
        </Svg>
      );

    case "sunglasses":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Rect x={6} y={26} width={21} height={15} rx={5} {...common} />
          <Rect x={37} y={26} width={21} height={15} rx={5} {...common} />
          <Path d="M27 30 C29 27.5 35 27.5 37 30" {...line} strokeWidth={2} />
          <Path d="M6 29 L2 26 M58 29 L62 26" {...line} strokeWidth={2} />
        </Svg>
      );

    case "watch":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Rect x={24} y={5} width={16} height={13} rx={3} {...common} />
          <Rect x={24} y={46} width={16} height={13} rx={3} {...common} />
          <Circle cx={32} cy={32} r={13} {...common} />
          <Path d="M32 32 V24.5 M32 32 H37.5" {...line} />
        </Svg>
      );

    case "tote":
      return (
        <Svg width={size} height={size} viewBox="0 0 64 64">
          <Path d="M14 24 H50 L46 55 H18 Z" {...common} />
          <Path d="M23 24 C23 11 31 11 31 24 M33 24 C33 11 41 11 41 24" {...line} strokeWidth={2.2} />
          <Path d="M20 32 H44" {...line} />
        </Svg>
      );
  }
}
