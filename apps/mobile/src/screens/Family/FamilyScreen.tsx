import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { familyApi } from "@/api/family";
import { CheckIcon, PlusIcon } from "@/components/icons";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { useAccent } from "@/state/theme";
import { fonts, glass, palette, radii, spacing } from "@/theme";

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Monogram avatar — initial in a tinted glass ring (no people emojis). */
function Monogram({ name, tint }: { name: string; tint: string }) {
  return (
    <View style={[styles.monogram, { borderColor: tint }]}>
      <Text style={[styles.monogramText, { color: tint }]}>
        {name.trim().charAt(0).toUpperCase() || "?"}
      </Text>
    </View>
  );
}

export function FamilyScreen() {
  const nav = useNavigation<Nav>();
  const profile = useActiveProfile();
  const accent = useAccent().color;
  const members = useQuery({ queryKey: ["family"], queryFn: familyApi.list });

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>FAMILY</Text>
          <Text style={styles.title}>WHO&apos;S STYLING?</Text>
        </View>
        <Pressable
          style={[styles.addButton, { backgroundColor: accent }]}
          onPress={() => nav.navigate("AddMember")}
        >
          <PlusIcon size={14} color="#0A0B0E" />
          <Text style={styles.addButtonText}>ADD</Text>
        </Pressable>
      </View>

      <Pressable
        style={[styles.row, profile.ownerKind === "user" && { borderColor: accent }]}
        onPress={() => profile.reset()}
      >
        <Monogram name="You" tint={accent} />
        <View style={{ flex: 1 }}>
          <Text style={styles.rowName}>You</Text>
          <View style={[styles.kindTag, { borderColor: accent }]}>
            <Text style={[styles.kindTagText, { color: accent }]}>GUARDIAN</Text>
          </View>
        </View>
        {profile.ownerKind === "user" && <CheckIcon size={14} color={accent} />}
      </Pressable>

      <FlatList
        data={members.data ?? []}
        keyExtractor={(m) => m.id}
        renderItem={({ item }) => {
          const active = profile.ownerId === item.id;
          return (
            <Pressable
              style={[styles.row, active && { borderColor: accent }]}
              onPress={() => profile.setFamilyMember(item)}
            >
              <Monogram name={item.display_name} tint={active ? accent : palette.textMuted} />
              <View style={{ flex: 1 }}>
                <Text style={styles.rowName}>{item.display_name}</Text>
                <Text style={styles.rowKind}>
                  {item.kind.toUpperCase()}
                  {item.kid_mode && "  ·  KID MODE"}
                </Text>
              </View>
              {active && <CheckIcon size={14} color={accent} />}
            </Pressable>
          );
        }}
        ListEmptyComponent={
          !members.isLoading ? (
            <Text style={styles.empty}>
              Add a sub-profile for a family member. Kid sub-profiles are COPPA-protected.
            </Text>
          ) : null
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "transparent" },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing(5),
  },
  eyebrow: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 2.5,
  },
  title: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 24,
    marginTop: 6,
    letterSpacing: 0.5,
  },
  addButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1.5),
    paddingHorizontal: spacing(3.5),
    paddingVertical: spacing(2),
    borderRadius: radii.sm,
  },
  addButtonText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 11.5,
    letterSpacing: 1.5,
  },
  row: {
    ...glass,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(3.5),
    padding: spacing(4),
    marginHorizontal: spacing(5),
    marginBottom: spacing(2.5),
    borderRadius: radii.md,
  },
  monogram: {
    width: 42,
    height: 42,
    borderRadius: 21,
    borderWidth: 1.5,
    backgroundColor: palette.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  monogramText: { fontFamily: fonts.display, fontSize: 16 },
  rowName: { color: palette.text, fontFamily: fonts.bodyBold, fontSize: 15.5 },
  kindTag: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: spacing(1.5),
    paddingVertical: 2,
    marginTop: spacing(1.5),
  },
  kindTagText: { fontFamily: fonts.mono, fontSize: 8.5, letterSpacing: 1.8 },
  rowKind: {
    color: palette.textMuted,
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1.2,
    marginTop: spacing(1.5),
  },
  empty: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    padding: spacing(6),
    textAlign: "center",
    lineHeight: 20,
  },
});
