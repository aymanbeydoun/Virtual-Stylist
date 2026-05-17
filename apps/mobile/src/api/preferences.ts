import { api } from "@/api/client";
import type { OwnerKind, Style } from "@/api/types";

export interface StylePreference {
  preferred_style: Style | null;
  owner_kind: OwnerKind;
  owner_id: string;
}

export const preferencesApi = {
  async getStyle(owner: { kind: OwnerKind; id?: string }) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    return api<StylePreference>(`/preferences/style?${params.toString()}`);
  },

  async setStyle(owner: { kind: OwnerKind; id?: string }, style: Style | null) {
    return api<StylePreference>("/preferences/style", {
      method: "PUT",
      json: {
        preferred_style: style,
        owner_kind: owner.kind,
        owner_id: owner.id,
      },
    });
  },
};
