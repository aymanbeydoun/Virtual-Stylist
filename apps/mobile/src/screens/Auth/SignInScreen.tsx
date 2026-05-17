import { Ionicons } from "@expo/vector-icons";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  AUTH0_CONFIG,
  auth0Discovery,
  buildRedirectUri,
  exchangeCode,
} from "@/api/auth0";
import { useAuth } from "@/state/auth";
import { palette, radii, spacing } from "@/theme";

// Required for the system browser to redirect back to the app reliably.
WebBrowser.maybeCompleteAuthSession();

export function SignInScreen() {
  const signInWithAuth0 = useAuth((s) => s.signInWithAuth0);
  const signInAsDev = useAuth((s) => s.signInAsDev);
  const [devValue, setDevValue] = useState("");
  const [auth0Busy, setAuth0Busy] = useState(false);

  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    AUTH0_CONFIG,
    auth0Discovery,
  );

  // When the browser closes with `success`, the SDK gives us a `code` we
  // exchange for the actual tokens. PKCE verifier lives on the request object.
  useEffect(() => {
    if (response?.type !== "success" || !request) return;
    const code = response.params.code;
    const verifier = request.codeVerifier;
    if (!code || !verifier) return;

    setAuth0Busy(true);
    exchangeCode(code, verifier)
      .then((tokens) => signInWithAuth0(tokens))
      .catch((err) =>
        Alert.alert(
          "Sign-in failed",
          err instanceof Error ? err.message : "Try again.",
        ),
      )
      .finally(() => setAuth0Busy(false));
  }, [response, request, signInWithAuth0]);

  const onAuth0Press = async () => {
    setAuth0Busy(true);
    try {
      const result = await promptAsync();
      if (result.type === "cancel" || result.type === "dismiss") {
        setAuth0Busy(false);
      } else if (result.type === "error") {
        Alert.alert(
          "Sign-in failed",
          result.error?.message ?? "Auth0 reported an error.",
        );
        setAuth0Busy(false);
      }
    } catch (err) {
      Alert.alert(
        "Couldn't open sign-in",
        err instanceof Error ? err.message : "Try again.",
      );
      setAuth0Busy(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.inner}>
        <Text style={styles.title}>Virtual Stylist</Text>
        <Text style={styles.subtitle}>Sign in to your closet.</Text>

        <Pressable
          style={[styles.primary, (!request || auth0Busy) && styles.primaryDisabled]}
          disabled={!request || auth0Busy}
          onPress={onAuth0Press}
        >
          {auth0Busy ? (
            <ActivityIndicator color={palette.onAccent} />
          ) : (
            <>
              <Ionicons name="log-in-outline" size={18} color={palette.onAccent} />
              <Text style={styles.primaryText}>Sign in / Sign up</Text>
            </>
          )}
        </Pressable>

        <Text style={styles.tinyHint}>
          Email, social, or passkey. Powered by Auth0.
        </Text>

        <View style={styles.divider}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerLabel}>OR</Text>
          <View style={styles.dividerLine} />
        </View>

        <Text style={styles.devLabel}>Dev mode</Text>
        <TextInput
          style={styles.input}
          placeholder="Nickname (e.g. ayman)"
          placeholderTextColor={palette.textMuted}
          value={devValue}
          onChangeText={setDevValue}
          autoCapitalize="none"
        />
        <Pressable
          style={[styles.secondary, !devValue && styles.secondaryDisabled]}
          disabled={!devValue}
          onPress={() => signInAsDev(devValue.trim())}
        >
          <Text style={styles.secondaryText}>Continue as dev user</Text>
        </Pressable>

        <Text style={styles.redirectHint} selectable>
          Redirect URI: {buildRedirectUri()}
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  inner: { flex: 1, padding: spacing(6), justifyContent: "center" },
  title: { fontSize: 36, fontWeight: "700", color: palette.text, marginBottom: spacing(2) },
  subtitle: { color: palette.textMuted, marginBottom: spacing(8) },
  primary: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing(2),
  },
  primaryDisabled: { opacity: 0.5 },
  primaryText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
  tinyHint: {
    color: palette.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: spacing(2),
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: spacing(8),
    gap: spacing(3),
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: palette.surfaceAlt },
  dividerLabel: { color: palette.textMuted, fontSize: 12, letterSpacing: 1 },
  devLabel: {
    color: palette.textMuted,
    fontSize: 11,
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: spacing(2),
  },
  input: {
    backgroundColor: palette.surface,
    color: palette.text,
    padding: spacing(4),
    borderRadius: radii.md,
    marginBottom: spacing(3),
  },
  secondary: {
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
  },
  secondaryDisabled: { opacity: 0.4 },
  secondaryText: { color: palette.text, fontWeight: "600", fontSize: 15 },
  redirectHint: {
    color: palette.textMuted,
    fontSize: 9,
    marginTop: spacing(8),
    textAlign: "center",
    fontFamily: "Menlo",
  },
});
