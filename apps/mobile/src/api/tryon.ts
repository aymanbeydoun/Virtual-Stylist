import { api } from "@/api/client";
import type {
  Angle,
  BasePhoto,
  BasePhotoSet,
  OutfitTryon,
  OutfitTryonSet,
  OwnerKind,
} from "@/api/types";

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

  /**
   * Commit a base photo. When `angle` is provided the photo is filed in the
   * per-angle map. Omitting `angle` behaves like the legacy single-photo
   * path (writes to `base_photo_key` AND mirrors as the "front" angle).
   */
  async commitBasePhoto(
    objectKey: string,
    owner: { kind: OwnerKind; id?: string },
    angle?: Angle,
  ) {
    return api<BasePhoto>("/tryon/base-photo", {
      method: "POST",
      json: {
        object_key: objectKey,
        owner_kind: owner.kind,
        owner_id: owner.id,
        angle,
      },
    });
  },

  async getBasePhoto(owner: { kind: OwnerKind; id?: string }) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    return api<BasePhoto>(`/tryon/base-photo?${params.toString()}`);
  },

  /** Return every uploaded angle for the owner. */
  async getBasePhotoSet(owner: { kind: OwnerKind; id?: string }) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    return api<BasePhotoSet>(`/tryon/base-photos?${params.toString()}`);
  },

  /**
   * Kick off render(s). By default the server renders only the FRONT angle
   * (or first available) — one render takes ~60-90s. Multi-angle is opt-in
   * because fanning out to 4 angles can take 4-12 minutes total against
   * Replicate's serialized semaphore.
   *
   * Pass `allAngles: true` to render every uploaded angle.
   */
  async requestTryon(outfitId: string, opts?: { allAngles?: boolean }) {
    const qs = opts?.allAngles ? "?all_angles=true" : "";
    return api<OutfitTryonSet>(`/tryon/outfits/${outfitId}/tryon${qs}`, {
      method: "POST",
    });
  },

  /** Back-compat: single-photo flow returns the front render (or last fallback). */
  async getLatestTryon(outfitId: string) {
    return api<OutfitTryon>(`/tryon/outfits/${outfitId}/tryon`);
  },

  /** New: all per-angle renders for this outfit's most recent try-on batch. */
  async getLatestTryonSet(outfitId: string) {
    return api<OutfitTryonSet>(`/tryon/outfits/${outfitId}/tryons`);
  },
};
