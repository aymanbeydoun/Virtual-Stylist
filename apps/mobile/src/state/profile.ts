import { create } from "zustand";

import type { FamilyMember, OwnerKind } from "@/api/types";

interface ActiveProfileState {
  ownerKind: OwnerKind;
  ownerId: string | null;
  ownerLabel: string;
  isKidMode: boolean;
  setOwner: (input: { kind: OwnerKind; id?: string; label: string; kidMode?: boolean }) => void;
  setFamilyMember: (member: FamilyMember) => void;
  reset: () => void;
}

export const useActiveProfile = create<ActiveProfileState>((set) => ({
  ownerKind: "user",
  ownerId: null,
  ownerLabel: "You",
  isKidMode: false,
  setOwner: ({ kind, id, label, kidMode }) =>
    set({ ownerKind: kind, ownerId: id ?? null, ownerLabel: label, isKidMode: kidMode ?? false }),
  setFamilyMember: (member) =>
    set({
      ownerKind: "family_member",
      ownerId: member.id,
      ownerLabel: member.display_name,
      isKidMode: member.kind === "kid" && member.kid_mode,
    }),
  reset: () => set({ ownerKind: "user", ownerId: null, ownerLabel: "You", isKidMode: false }),
}));
