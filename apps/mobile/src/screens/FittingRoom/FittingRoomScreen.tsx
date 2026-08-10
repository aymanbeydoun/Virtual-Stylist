import { RouteProp, useNavigation, useRoute } from "@react-navigation/native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { Image } from "expo-image";
import { useRef, useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withDecay,
} from "react-native-reanimated";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";

import { GarmentIcon } from "@/components/GarmentIcon";
import { CloseIcon, FlipIcon, Rotate360Icon } from "@/components/icons";
import { DEMO_CLOSET, type DemoItem, type DemoSlot } from "@/data/demoCloset";
import { hapticPress, hapticSuccess } from "@/lib/haptics";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useAccent } from "@/state/theme";
import { fonts, palette, radii, spacing } from "@/theme";

/**
 * THE FITTING ROOM — STaiLE ME's spatial try-on.
 *
 * State machine:  PERMISSION → ALIGN → FITTED
 *
 * ALIGN   — deep-canvas camera view (#050505 frame) with an architectural
 *           silhouette guide. Because the user aligns their body to the guide,
 *           the captured photo's body zones are known without any ML.
 * FITTED  — the outfit's garment vectors are anchored onto those body zones
 *           over the photo. A pan gesture spins the garment stack in 3D
 *           perspective (right-drag = clockwise) for kinetic inspection.
 *
 * v1 runs fully on-device in Expo Go. True body-geometry draping and full
 * user-model rotation come with the cloud engine + dev build — see
 * docs/FITTING_ROOM_ARCHITECTURE.md.
 */
type Phase = "align" | "fitted";

const INK = "#050505";
const GUIDE = "rgba(255,255,255,0.55)";

/** Garment anchors as fractions of the frame — matched to the align guide. */
const FIT: Record<DemoSlot, { left: number; top: number; w: number; rot: string; z: number }> = {
  outerwear: { left: 0.06, top: 0.27, w: 0.44, rot: "-6deg", z: 3 },
  top: { left: 0.3, top: 0.28, w: 0.42, rot: "0deg", z: 2 },
  dress: { left: 0.27, top: 0.27, w: 0.48, rot: "0deg", z: 2 },
  bottom: { left: 0.31, top: 0.47, w: 0.4, rot: "0deg", z: 1 },
  shoes: { left: 0.35, top: 0.75, w: 0.3, rot: "0deg", z: 1 },
  accessory: { left: 0.65, top: 0.13, w: 0.17, rot: "8deg", z: 4 },
};

/** Minimal architectural full-body silhouette guide. */
function SilhouetteGuide() {
  const s = { stroke: GUIDE, strokeWidth: 1.4, fill: "none" as const, strokeDasharray: "6 7" };
  return (
    <Svg
      width="100%"
      height="100%"
      viewBox="0 0 200 400"
      preserveAspectRatio="xMidYMid meet"
      pointerEvents="none"
    >
      <Circle cx={100} cy={52} r={23} {...s} />
      <Path d="M63 96 Q100 84 137 96" {...s} />
      <Path d="M64 96 L58 205 M136 96 L142 205" {...s} />
      <Path d="M58 205 Q100 220 142 205" {...s} />
      <Path d="M62 100 L42 195 M138 100 L158 195" {...s} />
      <Path d="M80 218 L72 338 M97 222 L93 338 M103 222 L107 338 M120 218 L128 338" {...s} />
      <Path d="M64 348 H96 M104 348 H136" {...s} />
      {/* Corner brackets */}
      <Path d="M14 24 V10 H28 M172 10 H186 V24 M186 376 V390 H172 M28 390 H14 V376" stroke={GUIDE} strokeWidth={2} fill="none" />
    </Svg>
  );
}

export function FittingRoomScreen() {
  const nav = useNavigation();
  const route = useRoute<RouteProp<RootStackParamList, "FittingRoom">>();
  const accent = useAccent().color;
  const { width } = useWindowDimensions();
  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<Phase>("align");
  const [facing, setFacing] = useState<"back" | "front">("back");
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cameraRef = useRef<CameraView>(null);

  const items: DemoItem[] = route.params.itemIds
    .map((id) => DEMO_CLOSET.find((i) => i.id === id))
    .filter((i): i is DemoItem => Boolean(i));

  // 360° kinetic inspection — right-drag spins clockwise, with momentum.
  const rotY = useSharedValue(0);
  const spin = Gesture.Pan()
    .onChange((e) => {
      rotY.value += e.changeX * 0.45;
    })
    .onEnd((e) => {
      rotY.value = withDecay({ velocity: e.velocityX * 0.45, deceleration: 0.998 });
    });
  const spinStyle = useAnimatedStyle(() => ({
    transform: [{ perspective: 750 }, { rotateY: `${rotY.value}deg` }],
  }));

  const capture = async () => {
    if (busy || !cameraRef.current) return;
    setBusy(true);
    hapticPress();
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
      if (photo?.uri) {
        setPhotoUri(photo.uri);
        setPhase("fitted");
        rotY.value = 0;
        hapticSuccess();
      }
    } catch {
      // Camera hiccup — stay in align phase so the user can retry.
    } finally {
      setBusy(false);
    }
  };

  if (!permission) {
    return <View style={styles.root} />;
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.permissionBox}>
          <Text style={styles.instruction}>THE FITTING ROOM NEEDS YOUR CAMERA</Text>
          <Text style={styles.permissionHint}>
            Your photo stays on this phone — it is never uploaded.
          </Text>
          <Pressable
            style={[styles.primaryBtn, { backgroundColor: accent }]}
            onPress={() => requestPermission()}
          >
            <Text style={styles.primaryBtnText}>ENABLE CAMERA</Text>
          </Pressable>
          <Pressable style={styles.ghostBtn} onPress={() => nav.goBack()}>
            <Text style={styles.ghostBtnText}>NOT NOW</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      {/* Top bar */}
      <View style={styles.topBar}>
        <Pressable style={styles.iconBtn} onPress={() => nav.goBack()} accessibilityLabel="Close">
          <CloseIcon size={17} />
        </Pressable>
        <Text style={styles.title}>THE FITTING ROOM</Text>
        {phase === "align" ? (
          <Pressable
            style={styles.iconBtn}
            onPress={() => setFacing((f) => (f === "back" ? "front" : "back"))}
            accessibilityLabel="Flip camera"
          >
            <FlipIcon size={17} />
          </Pressable>
        ) : (
          <View style={styles.iconBtn}>
            <Rotate360Icon size={18} color={accent} />
          </View>
        )}
      </View>

      {/* Frame */}
      <View style={styles.frame}>
        {phase === "align" ? (
          <>
            <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing={facing} />
            <View style={StyleSheet.absoluteFill}>
              <SilhouetteGuide />
            </View>
            <View style={styles.instructions} pointerEvents="none">
              <Text style={styles.instruction}>ALIGN FULL-BODY PROFILE</Text>
              <Text style={[styles.instruction, styles.instructionDim]}>ENSURE CLEAR LIGHTING</Text>
            </View>
          </>
        ) : (
          <GestureDetector gesture={spin}>
            <View style={StyleSheet.absoluteFill}>
              {photoUri && (
                <Image source={{ uri: photoUri }} style={StyleSheet.absoluteFill} contentFit="cover" />
              )}
              <View style={styles.fitScrim} pointerEvents="none" />
              <Animated.View style={[StyleSheet.absoluteFill, spinStyle]} pointerEvents="none">
                {items.map((item) => {
                  const a = FIT[item.slot];
                  return (
                    <View
                      key={item.id}
                      style={{
                        position: "absolute",
                        left: a.left * width,
                        top: `${a.top * 100}%`,
                        zIndex: a.z,
                        transform: [{ rotate: a.rot }],
                      }}
                    >
                      <GarmentIcon kind={item.icon} color={item.color} size={a.w * width} />
                    </View>
                  );
                })}
              </Animated.View>
              <View style={styles.inspectHint} pointerEvents="none">
                <Rotate360Icon size={15} color={accent} />
                <Text style={[styles.instruction, { color: accent }]}>DRAG TO INSPECT — 360°</Text>
              </View>
            </View>
          </GestureDetector>
        )}
      </View>

      {/* Bottom controls */}
      <View style={styles.controls}>
        {phase === "align" ? (
          <Pressable
            style={[styles.shutter, { borderColor: accent }, busy && { opacity: 0.4 }]}
            onPress={capture}
            disabled={busy}
            accessibilityLabel="Capture"
          >
            <View style={[styles.shutterCore, { backgroundColor: accent }]} />
          </Pressable>
        ) : (
          <View style={styles.fittedRow}>
            <Pressable style={styles.ghostBtn} onPress={() => setPhase("align")}>
              <Text style={styles.ghostBtnText}>RESCAN</Text>
            </Pressable>
            <Pressable
              style={[styles.primaryBtn, { backgroundColor: accent }]}
              onPress={() => nav.goBack()}
            >
              <Text style={styles.primaryBtnText}>DONE</Text>
            </Pressable>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: INK },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(3),
  },
  title: { color: palette.text, fontFamily: fonts.display, fontSize: 13, letterSpacing: 2 },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: "rgba(255,255,255,0.06)",
    alignItems: "center",
    justifyContent: "center",
  },
  frame: {
    flex: 1,
    marginHorizontal: spacing(3),
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: "#000",
    borderWidth: 1,
    borderColor: palette.hairlineFaint,
  },
  instructions: {
    position: "absolute",
    top: spacing(4),
    left: 0,
    right: 0,
    alignItems: "center",
    gap: spacing(1),
  },
  instruction: {
    color: palette.text,
    fontFamily: fonts.mono,
    fontSize: 10.5,
    letterSpacing: 2.5,
    textAlign: "center",
  },
  instructionDim: { color: palette.textMuted },
  fitScrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(5,5,5,0.18)" },
  inspectHint: {
    position: "absolute",
    bottom: spacing(4),
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing(2),
  },
  controls: {
    paddingVertical: spacing(4),
    paddingHorizontal: spacing(5),
    alignItems: "center",
  },
  shutter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 3,
    alignItems: "center",
    justifyContent: "center",
  },
  shutterCore: { width: 56, height: 56, borderRadius: 28 },
  fittedRow: {
    flexDirection: "row",
    gap: spacing(3),
    width: "100%",
    justifyContent: "center",
  },
  primaryBtn: {
    paddingVertical: spacing(3.5),
    paddingHorizontal: spacing(8),
    borderRadius: radii.sm,
    alignItems: "center",
  },
  primaryBtnText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 12.5,
    letterSpacing: 2,
  },
  ghostBtn: {
    paddingVertical: spacing(3.5),
    paddingHorizontal: spacing(6),
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: "center",
  },
  ghostBtnText: {
    color: palette.text,
    fontFamily: fonts.bodyBold,
    fontSize: 12.5,
    letterSpacing: 2,
  },
  permissionBox: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing(8),
    gap: spacing(4),
  },
  permissionHint: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    fontSize: 13,
    textAlign: "center",
  },
});
