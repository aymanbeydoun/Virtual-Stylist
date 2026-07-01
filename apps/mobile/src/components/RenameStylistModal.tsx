import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useStylist } from "@/state/stylist";
import { palette, radii, spacing } from "@/theme";

/**
 * Small dialog for renaming the AI stylist. Opened by the pen icon next to the
 * "Chat to …" button.
 */
export function RenameStylistModal({
  visible,
  onClose,
  accent,
}: {
  visible: boolean;
  onClose: () => void;
  accent: string;
}) {
  const name = useStylist((s) => s.name);
  const setName = useStylist((s) => s.setName);
  const [draft, setDraft] = useState(name);

  const save = () => {
    setName(draft);
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.card} onPress={() => {}}>
          <Text style={styles.title}>Name your stylist ✏️</Text>
          <Text style={styles.subtitle}>
            Pick a name that feels like a friend. You can change it anytime.
          </Text>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="e.g. Stella"
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            autoFocus
            maxLength={20}
            returnKeyType="done"
            onSubmitEditing={save}
          />
          <View style={styles.row}>
            <Pressable style={styles.cancel} onPress={onClose}>
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable style={[styles.save, { backgroundColor: accent }]} onPress={save}>
              <Text style={styles.saveText}>Save</Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "center",
    padding: spacing(6),
  },
  card: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: spacing(5),
  },
  title: { color: palette.text, fontSize: 20, fontWeight: "700" },
  subtitle: { color: palette.textMuted, marginTop: spacing(2), fontSize: 13 },
  input: {
    backgroundColor: palette.background,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: palette.surfaceAlt,
    color: palette.text,
    padding: spacing(3),
    fontSize: 16,
    marginTop: spacing(4),
  },
  row: { flexDirection: "row", justifyContent: "flex-end", gap: spacing(3), marginTop: spacing(5) },
  cancel: { paddingVertical: spacing(3), paddingHorizontal: spacing(4), borderRadius: radii.md },
  cancelText: { color: palette.textMuted, fontWeight: "600" },
  save: { paddingVertical: spacing(3), paddingHorizontal: spacing(5), borderRadius: radii.md },
  saveText: { color: palette.background, fontWeight: "700" },
});
