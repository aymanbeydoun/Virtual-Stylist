import { BlurView } from "expo-blur";
import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useStylist } from "@/state/stylist";
import { fonts, palette, radii, spacing } from "@/theme";

/**
 * Rename dialog for the AI stylist — glassmorphism card over a blurred ink
 * backdrop, matching the dark-mode styling system.
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
      <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFill}>
        <Pressable style={styles.backdrop} onPress={onClose}>
          <Pressable style={styles.card} onPress={() => {}}>
            <Text style={styles.title}>NAME YOUR STYLIST</Text>
            <Text style={styles.subtitle}>
              Pick a name that feels like a friend. You can change it anytime.
            </Text>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="e.g. Stella"
              placeholderTextColor={palette.textMuted}
              style={[styles.input, { borderColor: accent }]}
              autoFocus
              maxLength={20}
              returnKeyType="done"
              onSubmitEditing={save}
            />
            <View style={styles.row}>
              <Pressable style={styles.cancel} onPress={onClose}>
                <Text style={styles.cancelText}>CANCEL</Text>
              </Pressable>
              <Pressable style={[styles.save, { backgroundColor: accent }]} onPress={save}>
                <Text style={styles.saveText}>SAVE</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </BlurView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(6,7,9,0.55)",
    justifyContent: "center",
    padding: spacing(6),
  },
  card: {
    backgroundColor: "rgba(20,22,28,0.92)",
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: radii.lg,
    padding: spacing(5),
  },
  title: {
    color: palette.text,
    fontFamily: fonts.display,
    fontSize: 17,
    letterSpacing: 1,
  },
  subtitle: {
    color: palette.textMuted,
    fontFamily: fonts.body,
    marginTop: spacing(2),
    fontSize: 13,
    lineHeight: 19,
  },
  input: {
    backgroundColor: "rgba(10,11,14,0.7)",
    borderRadius: radii.sm,
    borderWidth: 1,
    color: palette.text,
    padding: spacing(3),
    fontSize: 16,
    fontFamily: fonts.bodyMedium,
    marginTop: spacing(4),
  },
  row: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing(3),
    marginTop: spacing(5),
  },
  cancel: { paddingVertical: spacing(3), paddingHorizontal: spacing(4), borderRadius: radii.sm },
  cancelText: {
    color: palette.textMuted,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    letterSpacing: 1.5,
  },
  save: { paddingVertical: spacing(3), paddingHorizontal: spacing(5), borderRadius: radii.sm },
  saveText: {
    color: "#0A0B0E",
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    letterSpacing: 1.5,
  },
});
