import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/state/auth";
import { useAccent } from "@/state/theme";
import { palette, radii, spacing } from "@/theme";

export function SignInScreen() {
  const signIn = useAuth((s) => s.signIn);
  const accent = useAccent().color;
  const [value, setValue] = useState("");

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.inner}>
        <Text style={styles.title}>Staile Me</Text>
        <Text style={styles.subtitle}>
          Your personal AI stylist is ready! ✨ Pop in your name and let&apos;s
          create outfits you&apos;ll absolutely love!
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
          <Text style={styles.buttonText}>Let&apos;s go! 🎉</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  inner: { flex: 1, padding: spacing(6), justifyContent: "center" },
  title: { fontSize: 36, fontWeight: "700", color: palette.text, marginBottom: spacing(2) },
  subtitle: { color: palette.textMuted, marginBottom: spacing(8) },
  input: {
    backgroundColor: palette.surface,
    color: palette.text,
    padding: spacing(4),
    borderRadius: radii.md,
    marginBottom: spacing(4),
  },
  button: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.4 },
  buttonText: { color: palette.background, fontWeight: "700", fontSize: 16 },
});
