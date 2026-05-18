import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { familyApi } from "@/api/family";
import type { FamilyMemberKind } from "@/api/types";
import type { RootStackParamList } from "@/navigation/RootNavigator";
import { useActiveProfile } from "@/state/profile";
import { palette, radii, spacing } from "@/theme";

type IoniconName = React.ComponentProps<typeof Ionicons>["name"];

const KIND_ICON: Record<FamilyMemberKind | "guardian", IoniconName> = {
  guardian: "person-outline",
  adult: "person-outline",
  teen: "person-outline",
  kid: "happy-outline",
};

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function FamilyScreen() {
  const nav = useNavigation<Nav>();
  const profile = useActiveProfile();
  const members = useQuery({ queryKey: ["family"], queryFn: familyApi.list });

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>Family</Text>
          <Text style={styles.title}>Who&apos;s styling?</Text>
        </View>
        <Pressable style={styles.addButton} onPress={() => nav.navigate("AddMember")}>
          <Text style={styles.addButtonText}>+ Add</Text>
        </Pressable>
      </View>

      <Pressable
        style={[styles.row, profile.ownerKind === "user" && styles.rowActive]}
        onPress={() => profile.reset()}
      >
        <View style={styles.rowAvatar}>
          <Ionicons name={KIND_ICON.guardian} size={22} color={palette.text} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.rowName}>You</Text>
          <Text style={styles.rowKind}>Guardian</Text>
        </View>
        {profile.ownerKind === "user" && <Text style={styles.dot}>•</Text>}
      </Pressable>

      <FlatList
        data={members.data ?? []}
        keyExtractor={(m) => m.id}
        renderItem={({ item }) => {
          const active = profile.ownerId === item.id;
          return (
            <Pressable
              style={[styles.row, active && styles.rowActive]}
              onPress={() => profile.setFamilyMember(item)}
            >
              <View style={styles.rowAvatar}>
                <Ionicons name={KIND_ICON[item.kind]} size={22} color={palette.text} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowName}>{item.display_name}</Text>
                <Text style={styles.rowKind}>
                  {item.kind}
                  {item.kid_mode && " · Kid mode"}
                </Text>
              </View>
              {active && <Text style={styles.dot}>•</Text>}
            </Pressable>
          );
        }}
        ListEmptyComponent={
          !members.isLoading ? (
            <Text style={styles.empty}>
              Add a sub-profile for a child or teen. Kid sub-profiles are COPPA-protected.
            </Text>
          ) : null
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.background },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing(5),
  },
  eyebrow: { color: palette.textMuted, fontSize: 12, letterSpacing: 1, textTransform: "uppercase" },
  title: { color: palette.text, fontSize: 28, fontWeight: "700", marginTop: 4 },
  addButton: {
    backgroundColor: palette.accent,
    paddingHorizontal: spacing(4),
    paddingVertical: spacing(2),
    borderRadius: radii.pill,
  },
  addButtonText: { color: palette.onAccent, fontWeight: "700" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing(4),
    marginHorizontal: spacing(5),
    marginBottom: spacing(2),
    backgroundColor: palette.surface,
    borderRadius: radii.md,
  },
  rowActive: { borderWidth: 1, borderColor: palette.accent },
  rowAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: palette.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing(4),
  },
  rowName: { color: palette.text, fontWeight: "600", fontSize: 16 },
  rowKind: { color: palette.textMuted, fontSize: 12, textTransform: "capitalize" },
  dot: { color: palette.accent, fontSize: 30 },
  empty: { color: palette.textMuted, padding: spacing(6), textAlign: "center" },
});
