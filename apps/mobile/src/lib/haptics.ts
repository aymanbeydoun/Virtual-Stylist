import * as Haptics from "expo-haptics";

/**
 * Mechanical haptic rails — STaiLE ME's tactile signature.
 *
 * Every call is fire-and-forget and swallow-safe (no-ops on devices or
 * platforms without a haptic engine).
 */
const safe = (p: Promise<void>) => {
  p.catch(() => {});
};

/** Heavy authoritative click — vibe/occasion chips, big commitments. */
export function hapticHeavyClick() {
  safe(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy));
}

/** Medium press — primary CTAs (STaiLE ME). */
export function hapticPress() {
  safe(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
}

/** Low rolling tick — flicking a garment layer, like a steel clothing rack. */
export function hapticRackTick() {
  safe(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Soft));
}

/** Fine selection tick — rating tiers, swatches, small toggles. */
export function hapticSelect() {
  safe(Haptics.selectionAsync());
}

/** Success bloom — outfits ready. */
export function hapticSuccess() {
  safe(Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
}
