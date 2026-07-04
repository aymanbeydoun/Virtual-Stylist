import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/state/auth";
import { useAccent } from "@/state/theme";
import { fonts, palette, radii, spacing } from "@/theme";

export function SignInScreen() {
  const signIn = useAuth((s) => s.signIn);
  const accent = useAccent().color;
  const [value, setValue] = useState("");

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.inner}>
        <Text style={[styles.brandMark, { color: accent }]}>EST. 2026 — PERSONAL STYLING</Text>
        <Text style={styles.title}>STaiLE{"\n"}ME</Text>
        <Text style={styles.subtitle}>
          Your personal AI stylist is ready! Pop in your name and let&apos;s create
          outfits you&apos;ll absolutely love!
        </Text>
        <TextInput
          style={styles.input}
          placeholder="Your name"
          placeholderTextColor={palette.textMuted}
          value={value}
          onChangeText={setValue}
          autoCapitalize="words"
        />
        <Pressable
          style={[styles.button, { backgroundColor: accent }, !value && styles.buttonDisabled]}
          disabled={!value}
          onPress={() => signIn(value.trim())}
        >
          <Text style={styles.buttonText}>LET&apos;S GO</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  inner: { flex: 1, padding: spacing(6), justifyContent: "center" },
  brandMark: {
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 3,
    marginBottom: spacing(3),
  },
  title: {
    fontSize: 52,
    lineHeight: 56,
    fontFamily: fonts.display,
    color: palette.text,
    letterSpacing: 1,
    marginBottom: spacing(4),
  },
  subtitle: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    fontSize: 14.5,
    lineHeight: 22,
    marginBottom: spacing(8),
  },
  input: {
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
    color: palette.text,
    fontFamily: fonts.bodyMedium,
    fontSize: 15,
    padding: spacing(4),
    borderRadius: radii.sm,
    marginBottom: spacing(4),
  },
  button: {
    padding: spacing(4),
    borderRadius: radii.sm,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.35 },
  buttonText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 14,
    letterSpacing: 3,
  },
});
