import { LinearGradient } from "expo-linear-gradient";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CheckIcon } from "@/components/icons";
import { useAura } from "@/state/aura";
import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import {
  ACCENT_THEMES,
  BACKGROUND_DESIGNS,
  useAccent,
  useTheme,
  type BackgroundDesign,
} from "@/state/theme";
import { fonts, glass, palette, radii, spacing } from "@/theme";

export function YouScreen() {
  const signOut = useAuth((s) => s.signOut);
  const devUserId = useAuth((s) => s.devUserId);
  const profile = useActiveProfile();
  const accentId = useTheme((s) => s.accentId);
  const setAccent = useTheme((s) => s.setAccent);
  const backgroundId = useTheme((s) => s.backgroundId);
  const setBackground = useTheme((s) => s.setBackground);
  const accent = useAccent();
  const activeColor = accent.color;

  // Mirrors ThemeEngine's base stops exactly so previews match reality.
  const designStops = (d: BackgroundDesign): [string, string, ...string[]] =>
    (d.fromAccent ? [`${accent.color}40`, "#0A0B0E", "#060709"] : [...d.colors]) as [
      string,
      string,
      ...string[],
    ];

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={{ padding: spacing(5) }}>
        <Text style={styles.eyebrow}>YOU</Text>
        <Text style={styles.title}>{(devUserId ?? "").toUpperCase()}</Text>
        <Text style={styles.body}>ACTIVE PROFILE — {profile.ownerLabel.toUpperCase()}</Text>

        {/* Accent token dashboard — the ink canvas never moves; accents punch. */}
        <View style={styles.panel}>
          <Text style={styles.section}>ACCENT</Text>
          <Text style={styles.hint}>High-contrast elements shift instantly. The ink stays.</Text>
          <View style={styles.swatches}>
            {ACCENT_THEMES.map((t) => {
              const selected = t.id === accentId;
              return (
                <Pressable
                  key={t.id}
                  style={styles.swatchWrap}
                  onPress={() => setAccent(t.id)}
                  accessibilityLabel={`${t.name} accent`}
                >
                  <View
                    style={[
                      styles.swatch,
                      { backgroundColor: t.color },
                      selected && styles.swatchSelected,
                    ]}
                  >
                    {selected && <CheckIcon size={15} color="#0A0B0E" />}
                  </View>
                  <Text
                    style={[styles.swatchName, selected && { color: t.color }]}
                    numberOfLines={1}
                  >
                    {t.name.toUpperCase()}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* Background designs */}
        <View style={styles.panel}>
          <Text style={styles.section}>BACKDROP</Text>
          <Text style={styles.hint}>Give the ink canvas some character.</Text>
          <View style={styles.designs}>
            {BACKGROUND_DESIGNS.map((d) => {
              const selected = d.id === backgroundId;
              return (
                <Pressable
                  key={d.id}
                  style={styles.designWrap}
                  onPress={() => {
                    // Manual backdrop choice takes over from any live aura.
                    useAura.getState().setAura(null);
                    setBackground(d.id);
                  }}
                  accessibilityLabel={`${d.name} background`}
                >
                  <LinearGradient
                    colors={designStops(d)}
                    style={[styles.designPreview, selected && { borderColor: activeColor }]}
                  >
                    {selected && <CheckIcon size={14} color={activeColor} />}
                  </LinearGradient>
                  <Text style={[styles.designName, selected && { color: activeColor }]}>
                    {d.name.toUpperCase()}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <Pressable
          style={[styles.button, { backgroundColor: activeColor }]}
          onPress={() => signOut()}
        >
          <Text style={styles.buttonText}>SIGN OUT</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  eyebrow: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 2.5,
  },
  title: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 26,
    marginTop: 6,
    letterSpacing: 0.5,
  },
  body: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 10.5,
    letterSpacing: 1.5,
    marginTop: spacing(3),
  },
  panel: {
    ...glass,
    borderRadius: radii.lg,
    padding: spacing(4),
    marginTop: spacing(6),
  },
  section: {
    color: palette.text,
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2.5,
  },
  hint: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    fontSize: 12,
    marginTop: spacing(1),
    marginBottom: spacing(4),
  },
  swatches: { flexDirection: "row", flexWrap: "wrap", gap: spacing(3) },
  swatchWrap: { alignItems: "center", width: 62 },
  swatch: {
    width: 46,
    height: 46,
    borderRadius: radii.sm,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
  },
  swatchSelected: {
    borderWidth: 2,
    borderColor: "#F5F6F7",
  },
  swatchName: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 8.5,
    letterSpacing: 1.2,
    marginTop: spacing(1.5),
  },
  designs: { flexDirection: "row", flexWrap: "wrap", gap: spacing(3) },
  designWrap: { alignItems: "center", width: 92 },
  designPreview: {
    width: 92,
    height: 56,
    borderRadius: radii.sm,
    borderWidth: 1.5,
    borderColor: palette.hairline,
    alignItems: "center",
    justifyContent: "center",
  },
  designName: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 8.5,
    letterSpacing: 1.2,
    marginTop: spacing(1.5),
  },
  button: {
    padding: spacing(4),
    borderRadius: radii.sm,
    alignItems: "center",
    marginTop: spacing(8),
  },
  buttonText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2.5,
  },
});
