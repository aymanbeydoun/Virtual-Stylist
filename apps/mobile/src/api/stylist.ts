import { api } from "@/api/client";
import type { Destination, GenerateOutfitResponse, Mood, OwnerKind } from "@/api/types";

export const stylistApi = {
  async generate(
    owner: { kind: OwnerKind; id?: string },
    destination: Destination,
    mood: Mood,
    notes?: string,
  ) {
    return api<GenerateOutfitResponse>("/stylist/generate", {
      method: "POST",
      json: {
        destination,
        mood,
        notes,
        owner_kind: owner.kind,
        owner_id: owner.id,
      },
    });
  },

  async recordEvent(outfitId: string, kind: "worn" | "skipped" | "saved" | "regenerated") {
    return api<{ status: string }>(`/stylist/outfits/${outfitId}/events?kind=${kind}`, {
      method: "POST",
    });
  },
};
