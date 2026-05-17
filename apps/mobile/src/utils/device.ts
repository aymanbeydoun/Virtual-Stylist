import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * True when running inside the iOS Simulator (no camera, etc.).
 *
 * `Constants.deviceName` on iOS sims is "iPhone 17 Pro Simulator" or similar.
 * Falling back to Expo's executionEnvironment + Platform combo for safety on
 * older SDKs and Android emulators.
 */
export function isIosSimulator(): boolean {
  if (Platform.OS !== "ios") return false;
  const name = Constants.deviceName ?? "";
  if (name.toLowerCase().includes("simulator")) return true;
  // Legacy Expo SDK exposed this directly.
  const legacy = (Constants.platform as { ios?: { simulator?: boolean } } | undefined)?.ios;
  return legacy?.simulator === true;
}
