import { api } from "@/api/client";
import type { GapFinding, OwnerKind } from "@/api/types";

export const gapsApi = {
  async run(owner: { kind: OwnerKind; id?: string }) {
    return api<GapFinding[]>("/gaps/analyse", {
      method: "POST",
      json: { owner_kind: owner.kind, owner_id: owner.id },
    });
  },

  async list(owner: { kind: OwnerKind; id?: string }, includeDismissed = false) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    if (includeDismissed) params.set("include_dismissed", "true");
    return api<GapFinding[]>(`/gaps?${params.toString()}`);
  },

  async dismiss(gapId: string, owner: { kind: OwnerKind; id?: string }) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    return api<void>(`/gaps/${gapId}/dismiss?${params.toString()}`, { method: "POST" });
  },
};
