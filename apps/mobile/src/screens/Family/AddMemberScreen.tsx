import { useNavigation } from "@react-navigation/native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { familyApi } from "@/api/family";
import type { FamilyMemberKind } from "@/api/types";
import { palette, radii, spacing } from "@/theme";

const KINDS: FamilyMemberKind[] = ["kid", "teen", "adult"];

export function AddMemberScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<FamilyMemberKind>("kid");
  const [birthYear, setBirthYear] = useState("");
  const [consent, setConsent] = useState(false);

  const create = useMutation({
    mutationFn: () =>
      familyApi.create({
        display_name: name.trim(),
        kind,
        birth_year: birthYear ? Number(birthYear) : undefined,
        kid_mode: kind === "kid",
        consent_method: kind === "kid" ? "card_check" : undefined,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["family"] });
      nav.goBack();
    },
  });

  const requiresConsent = kind === "kid";
  const canSubmit = name.trim().length > 0 && (!requiresConsent || consent);

  return (
    <View style={styles.root}>
      <Text style={styles.label}>Name</Text>
      <TextInput
        style={styles.input}
        placeholder="First name only for kids"
        placeholderTextColor={palette.textMuted}
        value={name}
        onChangeText={setName}
      />

      <Text style={styles.label}>Profile type</Text>
      <View style={styles.row}>
        {KINDS.map((k) => (
          <Pressable
            key={k}
            style={[styles.kindChip, kind === k && styles.kindChipActive]}
            onPress={() => setKind(k)}
          >
            <Text style={[styles.kindText, kind === k && styles.kindTextActive]}>{k}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Birth year (optional, for sizing)</Text>
      <TextInput
        style={styles.input}
        placeholder="e.g. 2015"
        placeholderTextColor={palette.textMuted}
        value={birthYear}
        onChangeText={setBirthYear}
        keyboardType="number-pad"
      />

      {requiresConsent && (
        <View style={styles.consent}>
          <Switch value={consent} onValueChange={setConsent} />
          <Text style={styles.consentText}>
            I am the guardian and consent to a kid sub-profile under COPPA. No data is used for ads,
            and affiliate suggestions are off by default.
          </Text>
        </View>
      )}

      <Pressable
        style={[styles.submit, !canSubmit && styles.submitDisabled]}
        disabled={!canSubmit || create.isPending}
        onPress={() => create.mutate()}
      >
        <Text style={styles.submitText}>{create.isPending ? "Creating…" : "Create profile"}</Text>
      </Pressable>

      {create.isError && (
        <Text style={styles.error}>Failed: {(create.error as Error).message}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background, padding: spacing(5) },
  label: {
    color: palette.textMuted,
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginTop: spacing(4),
    marginBottom: spacing(2),
  },
  input: {
    backgroundColor: palette.surface,
    color: palette.text,
    padding: spacing(3),
    borderRadius: radii.md,
  },
  row: { flexDirection: "row", gap: spacing(2) },
  kindChip: {
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(2),
    borderRadius: radii.pill,
    backgroundColor: palette.surface,
  },
  kindChipActive: { backgroundColor: palette.accent },
  kindText: { color: palette.text, textTransform: "capitalize" },
  kindTextActive: { color: palette.onAccent, fontWeight: "700" },
  consent: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(3),
    marginTop: spacing(5),
    backgroundColor: palette.surface,
    padding: spacing(4),
    borderRadius: radii.md,
  },
  consentText: { color: palette.textMuted, flex: 1, fontSize: 13 },
  submit: {
    backgroundColor: palette.accent,
    padding: spacing(4),
    borderRadius: radii.md,
    alignItems: "center",
    marginTop: spacing(8),
  },
  submitDisabled: { opacity: 0.4 },
  submitText: { color: palette.onAccent, fontWeight: "700", fontSize: 16 },
  error: { color: palette.danger, marginTop: spacing(4) },
});
