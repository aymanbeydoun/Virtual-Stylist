import { api } from "@/api/client";
import type { GapFinding, OwnerKind } from "@/api/types";

export interface AffiliateSuggestion {
  id: string;
  gap_finding_id: string;
  provider: string;
  external_id: string;
  title: string;
  brand: string | null;
  image_url: string | null;
  price_minor: number | null;
  price_currency: string | null;
  affiliate_url: string;
  created_at: string;
}

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

  async suggestions(gapId: string) {
    return api<AffiliateSuggestion[]>(`/gaps/${gapId}/suggestions`);
  },

  async clickSuggestion(suggestionId: string) {
    return api<{ url: string }>(`/gaps/suggestions/${suggestionId}/click`, {
      method: "POST",
    });
  },
};
