# STaiLE ME — Spatial 360° Fitting Room Architecture

Specification acknowledgement and build plan for the "stAIle Me" virtual
try-on experience. **v1 is implemented and running in Expo Go today**
(`apps/mobile/src/screens/FittingRoom/FittingRoomScreen.tsx`); v2 requires the
cloud draping engine and an EAS development build. The existing app design
system is untouched — the fitting room composes the same ink canvas, glass
chrome, mono micro-copy, and accent tokens.

---

## 1. Component breakdown

```
StyleScreen
└── OutfitCard
    ├── OutfitCanvas          (flat-lay lookbook, flick-to-swap layers)
    └── [360 try-on action] ──navigate("FittingRoom", { itemIds })──┐
                                                                    ▼
FittingRoomScreen  (immersive, headerless, fade transition, #050505)
├── PermissionGate            camera consent; privacy promise (photo never leaves device)
├── TopBar                    close ✕ · THE FITTING ROOM · flip / 360 indicator
├── Frame                     letterboxed capture stage
│   ├── ALIGN phase
│   │   ├── CameraView        expo-camera live feed (front/back)
│   │   ├── SilhouetteGuide   dashed architectural body wireframe + corner brackets (SVG)
│   │   └── Instructions      "ALIGN FULL-BODY PROFILE" / "ENSURE CLEAR LIGHTING" (mono caps)
│   └── FITTED phase
│       ├── PhotoLayer        captured frame (expo-image, cover)
│       ├── GarmentStack      Animated.View — outfit vectors anchored per body zone
│       │   └── GarmentIcon×N slot-anchored (FIT map), z-ordered, layered
│       └── InspectHint       Rotate360Icon + "DRAG TO INSPECT — 360°"
└── Controls                  ALIGN: shutter (haptic) · FITTED: RESCAN / DONE
```

Supporting modules: `lib/haptics` (press/success rails), `components/icons`
(Close/Flip/Rotate360 glyphs), `data/demoCloset` (asset + slot registry).

## 2. State management

Single-screen finite state machine (React state; no global store needed —
the fitting session is ephemeral by design):

```
        grant                capture                     RESCAN
PERMISSION ──► ALIGN ────────────────► FITTED ──────────────► ALIGN
                 │  facing: back|front   │ photoUri: string      (photo discarded)
                 │  busy: bool (shutter) │ rotY: SharedValue<deg>
                 └── deny → exit         └── DONE → goBack()
```

- `phase: "align" | "fitted"` — the only mode switch; camera unmounts in
  FITTED (battery + privacy).
- `itemIds` arrive via route params (serializable); resolved against the
  closet registry at render, so a swapped outfit (flick-to-swap) tries on
  exactly what the canvas shows.
- Rotation lives on the UI thread as a Reanimated `SharedValue` — zero
  bridge traffic during gestures.
- Photos are held in memory/tmp only; nothing is persisted or uploaded in v1.

## 3. Gesture logic (360° kinetic inspection)

```ts
const rotY = useSharedValue(0);
const spin = Gesture.Pan()
  .onChange(e => { rotY.value += e.changeX * 0.45; })        // 1:1 finger lock
  .onEnd(e => { rotY.value = withDecay({                      // momentum spin
    velocity: e.velocityX * 0.45, deceleration: 0.998 }); });
// transform: [{ perspective: 750 }, { rotateY: `${rotY}deg` }]
```

- Right-drag → positive rotateY → clockwise; left-drag → counter-clockwise —
  matching the spec's mapping. Free-spin with decay covers full 360°+.
- v1 rotates the **garment stack in perspective** over the still photo (the
  brief's lock-step body rotation is impossible for a 2D photograph — see
  the v2 pipeline below for the honest path to it).

## 4. Alignment-anchored fitting (the v1 trick)

No on-device ML is needed to place garments credibly: the user aligns their
body to the silhouette guide, so body zones are known by construction. The
`FIT` map anchors each slot as fractions of the frame (top→torso,
bottom→legs, shoes→feet, outerwear offset overlay, accessory at head
height), z-ordered for organic layering.

## 5. v2 — true draping & body rotation (dev build + cloud)

| Stage | Tech | Notes |
|---|---|---|
| Pose estimation | On-device (Vision/ML Kit via dev build) | Replaces the FIT map with per-joint garment warping |
| Photoreal draping | Cloud GPU: IDM-VTON (see `VERVE_ARCHITECTURE.md` §4) | Real fabric drape, weight, occlusion |
| 360° body rotation | Cloud: single-image 3D avatar (gaussian splat / SMPL fit) streamed as a turnable mesh | True lock-step user+garment rotation |
| Background removal / auto-tagging (Module 3) | Cloud CV pipeline, already specced in the backend (`services/api` ingest worker + model gateway) | Closet digitization |

v1 ships the full UX shell (trigger → align → capture → inspect → done) so
v2 swaps rendering layers without changing the flow.
