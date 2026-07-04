import { useNavigation } from "@react-navigation/native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { familyApi } from "@/api/family";
import type { FamilyMemberKind } from "@/api/types";
import { useAccent } from "@/state/theme";
import { fonts, glass, palette, radii, spacing } from "@/theme";

const KINDS: FamilyMemberKind[] = ["kid", "teen", "adult"];

export function AddMemberScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const accent = useAccent().color;
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
      <Text style={styles.label}>NAME</Text>
      <TextInput
        style={styles.input}
        placeholder="First name only for kids"
        placeholderTextColor={palette.textMuted}
        value={name}
        onChangeText={setName}
      />

      <Text style={styles.label}>PROFILE TYPE</Text>
      <View style={styles.row}>
        {KINDS.map((k) => (
          <Pressable
            key={k}
            style={[
              styles.kindChip,
              kind === k && { backgroundColor: accent, borderColor: accent },
            ]}
            onPress={() => setKind(k)}
          >
            <Text style={[styles.kindText, kind === k && styles.kindTextActive]}>
              {k.toUpperCase()}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>BIRTH YEAR (OPTIONAL, FOR SIZING)</Text>
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
        style={[
          styles.submit,
          { backgroundColor: accent },
          !canSubmit && styles.submitDisabled,
        ]}
        disabled={!canSubmit || create.isPending}
        onPress={() => create.mutate()}
      >
        <Text style={styles.submitText}>
          {create.isPending ? "CREATING…" : "CREATE PROFILE"}
        </Text>
      </Pressable>

      {create.isError && (
        <Text style={styles.error}>Failed: {(create.error as Error).message}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent", padding: spacing(5) },
  label: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1.8,
    marginTop: spacing(4),
    marginBottom: spacing(2),
  },
  input: {
    ...glass,
    color: palette.text,
    fontFamily: fonts.body,
    fontSize: 14.5,
    padding: spacing(3),
    borderRadius: radii.sm,
  },
  row: { flexDirection: "row", gap: spacing(2) },
  kindChip: {
    ...glass,
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(2.5),
    borderRadius: radii.sm,
  },
  kindText: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11.5,
    letterSpacing: 1.2,
  },
  kindTextActive: { color: "#0A0B0E", fontFamily: fonts.bodyBold },
  consent: {
    ...glass,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(3),
    marginTop: spacing(5),
    padding: spacing(4),
    borderRadius: radii.md,
  },
  consentText: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    flex: 1,
    fontSize: 12.5,
    lineHeight: 18,
  },
  submit: {
    padding: spacing(4),
    borderRadius: radii.sm,
    alignItems: "center",
    marginTop: spacing(8),
  },
  submitDisabled: { opacity: 0.35 },
  submitText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2,
  },
  error: { color: palette.danger, fontFamily: fonts.body, marginTop: spacing(4) },
});
