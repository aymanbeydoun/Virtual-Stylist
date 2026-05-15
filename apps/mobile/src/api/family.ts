import { api } from "@/api/client";
import type { FamilyMember, FamilyMemberKind } from "@/api/types";

export const familyApi = {
  list: () => api<FamilyMember[]>("/family/members"),

  create: (input: {
    display_name: string;
    kind: FamilyMemberKind;
    birth_year?: number;
    kid_mode?: boolean;
    consent_method?: "card_check" | "signed_id" | "kba";
  }) => api<FamilyMember>("/family/members", { method: "POST", json: input }),

  remove: (id: string) => api<void>(`/family/members/${id}`, { method: "DELETE" }),
};
