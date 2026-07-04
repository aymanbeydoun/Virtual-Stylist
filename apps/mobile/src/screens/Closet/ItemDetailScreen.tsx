import { RouteProp, useRoute } from "@react-navigation/native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { wardrobeApi } from "@/api/wardrobe";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { fonts, glass, palette, radii, spacing } from "@/theme";

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export function ItemDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "ItemDetail">>();
  const profile = useActiveProfile();
  const qc = useQueryClient();
  const { itemId } = route.params;

  const item = useQuery({
    queryKey: ["wardrobe", profile.ownerKind, profile.ownerId],
    queryFn: () =>
      wardrobeApi.listItems({ kind: profile.ownerKind, id: profile.ownerId ?? undefined }),
    select: (items) => items.find((i) => i.id === itemId),
  });

  const correct = useMutation({
    mutationFn: ({ field, value }: { field: string; value: string }) =>
      wardrobeApi.correct(itemId, field, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wardrobe"] }),
  });

  const [category, setCategory] = useState("");

  if (!item.data) return <Text style={styles.loading}>Loading…</Text>;
  const it = item.data;

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: spacing(5) }}>
      {it.thumbnail_key && (
        <Image
          source={{ uri: `${baseUrl}/api/v1/wardrobe/_local_read/${it.thumbnail_key}` }}
          style={styles.image}
          contentFit="cover"
        />
      )}
      <Field label="Category" value={it.category ?? "—"} />
      <Field label="Pattern" value={it.pattern ?? "—"} />
      <Field label="Formality" value={it.formality?.toString() ?? "—"} />
      <Field label="Seasonality" value={it.seasonality.join(", ") || "—"} />
      <Field label="Colors" value={it.colors.map((c) => c.name).join(", ") || "—"} />

      <Text style={styles.section}>FIX A TAG</Text>
      <TextInput
        style={styles.input}
        placeholder={`Correct category (current: ${it.category ?? "—"})`}
        placeholderTextColor={palette.textMuted}
        value={category}
        onChangeText={setCategory}
        autoCapitalize="none"
      />
      <Pressable
        style={[styles.button, !category && styles.buttonDisabled]}
        disabled={!category}
        onPress={() => {
          correct.mutate({ field: "category", value: category });
          setCategory("");
        }}
      >
        <Text style={styles.buttonText}>SAVE CORRECTION</Text>
      </Pressable>
    </ScrollView>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <Text style={styles.fieldValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  loading: { color: palette.text, fontFamily: fonts.body, padding: spacing(6) },
  image: {
    width: "100%",
    aspectRatio: 1,
    borderRadius: radii.lg,
    backgroundColor: palette.surface,
    marginBottom: spacing(5),
  },
  field: { marginBottom: spacing(4) },
  fieldLabel: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 1.8,
  },
  fieldValue: { color: palette.text, fontFamily: fonts.bodyMedium, fontSize: 15.5, marginTop: 4 },
  section: {
    color: palette.text,
    fontFamily: fonts.bodyBold,
    fontSize: 13,
    letterSpacing: 2,
    marginTop: spacing(4),
  },
  input: {
    ...glass,
    color: palette.text,
    fontFamily: fonts.body,
    fontSize: 14.5,
    padding: spacing(3),
    borderRadius: radii.sm,
    marginVertical: spacing(3),
  },
  button: {
    backgroundColor: palette.accent,
    padding: spacing(3.5),
    borderRadius: radii.sm,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.35 },
  buttonText: {
    color: palette.background,
    fontFamily: fonts.bodyBold,
    fontSize: 12.5,
    letterSpacing: 2,
  },
});
