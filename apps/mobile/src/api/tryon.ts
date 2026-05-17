import { api } from "@/api/client";
import type { BasePhoto, OutfitTryon, OwnerKind } from "@/api/types";

export const tryonApi = {
  async createBasePhotoUploadUrl(
    contentType: string,
    owner: { kind: OwnerKind; id?: string },
  ) {
    return api<{ upload_url: string; object_key: string; expires_at: string }>(
      "/tryon/base-photo/upload-url",
      {
        method: "POST",
        json: { content_type: contentType, owner_kind: owner.kind, owner_id: owner.id },
      },
    );
  },

  async commitBasePhoto(objectKey: string, owner: { kind: OwnerKind; id?: string }) {
    return api<BasePhoto>("/tryon/base-photo", {
      method: "POST",
      json: { object_key: objectKey, owner_kind: owner.kind, owner_id: owner.id },
    });
  },

  async getBasePhoto(owner: { kind: OwnerKind; id?: string }) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    return api<BasePhoto>(`/tryon/base-photo?${params.toString()}`);
  },

  async requestTryon(outfitId: string) {
    return api<OutfitTryon>(`/tryon/outfits/${outfitId}/tryon`, { method: "POST" });
  },

  async getLatestTryon(outfitId: string) {
    return api<OutfitTryon>(`/tryon/outfits/${outfitId}/tryon`);
  },
};
