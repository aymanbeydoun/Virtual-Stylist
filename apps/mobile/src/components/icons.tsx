import Svg, { Circle, Line, Path, Rect } from "react-native-svg";

/**
 * Minimal geometric UI glyphs — sharp 1.5–2px strokes, no native emojis.
 * All icons draw on a 24×24 grid and take `size` + `color`.
 */
interface IconProps {
  size?: number;
  color?: string;
  strokeWidth?: number;
}

/** Clothes hanger — Closet tab. */
export function HangerIcon({ size = 22, color = "#F5F6F7", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 4.5a2 2 0 1 1 2-2M12 4.5v2.2M12 6.7 3.2 15.4a1.6 1.6 0 0 0 1.13 2.73h15.34a1.6 1.6 0 0 0 1.13-2.73L12 6.7Z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Four-point spark — Style tab. */
export function SparkIcon({ size = 22, color = "#F5F6F7", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 2.5c.7 4.6 2.9 6.8 7.5 7.5-4.6.7-6.8 2.9-7.5 7.5-.7-4.6-2.9-6.8-7.5-7.5 4.6-.7 6.8-2.9 7.5-7.5Z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
      <Circle cx={18.6} cy={19} r={2} stroke={color} strokeWidth={strokeWidth} />
    </Svg>
  );
}

/** Two heads — Family tab. */
export function FamilyIcon({ size = 22, color = "#F5F6F7", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx={9} cy={8.5} r={3.2} stroke={color} strokeWidth={strokeWidth} />
      <Path
        d="M3.2 19.5c.7-3 3-4.7 5.8-4.7s5.1 1.7 5.8 4.7"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <Circle cx={16.8} cy={9.6} r={2.5} stroke={color} strokeWidth={strokeWidth} />
      <Path
        d="M16.4 14.9c2.4.2 4 1.7 4.5 4.1"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
    </Svg>
  );
}

/** Single head + shoulders — You tab. */
export function PersonIcon({ size = 22, color = "#F5F6F7", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx={12} cy={8} r={3.6} stroke={color} strokeWidth={strokeWidth} />
      <Path
        d="M4.8 20c.9-3.6 3.8-5.6 7.2-5.6s6.3 2 7.2 5.6"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
    </Svg>
  );
}

/** Sharp check mark. */
export function CheckIcon({ size = 16, color = "#F5F6F7", strokeWidth = 2.4 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4.5 12.8 9.6 18 19.5 6.5"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Minimal sharp lock — square body, thin shackle, keyhole slit. */
export function LockIcon({ size = 14, color = "#8A8F98", strokeWidth = 1.6 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M7.5 10V7.2a4.5 4.5 0 0 1 9 0V10" stroke={color} strokeWidth={strokeWidth} />
      <Rect x={5} y={10} width={14} height={10.5} rx={1.5} stroke={color} strokeWidth={strokeWidth} />
      <Line x1={12} y1={13.4} x2={12} y2={17} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  );
}

/** Pen nib — rename action. */
export function PenIcon({ size = 18, color = "#F5F6F7", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M14.5 4.8 19.2 9.5 8.3 20.4l-5.1 1.4 1.4-5.1L15.5 5.8a2.05 2.05 0 0 1 3.7 3.7"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Chat bubble. */
export function ChatIcon({ size = 18, color = "#F5F6F7", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5c-1.5 0-2.9-.3-4.1-.9L3 20.5l1.4-5.4A8.5 8.5 0 1 1 21 11.5Z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Send arrow (paper-plane point). */
export function SendIcon({ size = 18, color = "#0A0B0E", strokeWidth = 1.9 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 12 20 4l-4.5 16-4-6.5L4 12Zm7.5 1.5L20 4"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Forward chevron. */
export function ChevronIcon({ size = 16, color = "#8A8F98", strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="m9 5 7 7-7 7"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Flame — streak indicator. */
export function FlameIcon({ size = 16, color = "#FF7847", strokeWidth = 1.8 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 21.5c-4 0-6.5-2.6-6.5-6.2 0-2.6 1.7-4.6 3-6.4C9.6 7.4 10.6 5.4 10.4 3c3.4 1.8 4.4 4.5 4.2 7 1-.3 1.8-1 2.2-2.2 1.2 1.6 1.7 3.6 1.7 5.5 0 3.6-2.5 6.2-6.5 6.2Z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Plus. */
export function PlusIcon({ size = 16, color = "#0A0B0E", strokeWidth = 2.2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 5v14M5 12h14" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  );
}
