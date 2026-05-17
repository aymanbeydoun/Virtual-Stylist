import { api } from "@/api/client";
import type { OwnerKind, Style } from "@/api/types";

export type BodyShape =
  | "rectangle"
  | "hourglass"
  | "pear"
  | "apple"
  | "inverted_triangle"
  | "athletic";

export interface StylePreference {
  preferred_style: Style | null;
  body_shape: BodyShape | null;
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

  async setBodyShape(owner: { kind: OwnerKind; id?: string }, shape: BodyShape | null) {
    return api<StylePreference>("/preferences/body-shape", {
      method: "PUT",
      json: {
        body_shape: shape,
        owner_kind: owner.kind,
        owner_id: owner.id,
      },
    });
  },
};
