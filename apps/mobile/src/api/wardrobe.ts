import { api } from "@/api/client";
import type { OwnerKind, UploadUrlResponse, WardrobeItem } from "@/api/types";

export const wardrobeApi = {
  async createUploadUrl(contentType: string, owner: { kind: OwnerKind; id?: string }) {
    return api<UploadUrlResponse>("/wardrobe/upload-url", {
      method: "POST",
      json: { content_type: contentType, owner_kind: owner.kind, owner_id: owner.id },
    });
  },

  async uploadBytes(uploadUrl: string, bytes: Blob, contentType: string) {
    const isAbsolute = uploadUrl.startsWith("http");
    const target = isAbsolute
      ? uploadUrl
      : `${process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000"}${uploadUrl}`;

    const formData = new FormData();
    formData.append("file", bytes, "upload.jpg");
    const resp = await fetch(target, {
      method: "PUT",
      body: isAbsolute ? bytes : formData,
      headers: isAbsolute ? { "Content-Type": contentType } : undefined,
    });
    if (!resp.ok) throw new Error(`upload failed: ${resp.status}`);
  },

  async createItem(objectKey: string, owner: { kind: OwnerKind; id?: string }) {
    return api<WardrobeItem>("/wardrobe/items", {
      method: "POST",
      json: { object_key: objectKey, owner_kind: owner.kind, owner_id: owner.id },
    });
  },

  async listItems(owner: { kind: OwnerKind; id?: string }, category?: string) {
    const params = new URLSearchParams({ owner_kind: owner.kind });
    if (owner.id) params.set("owner_id", owner.id);
    if (category) params.set("category", category);
    return api<WardrobeItem[]>(`/wardrobe/items?${params.toString()}`);
  },

  async correct(itemId: string, field: string, newValue: string) {
    await api<void>(`/wardrobe/items/${itemId}/corrections`, {
      method: "POST",
      json: { field, new_value: newValue },
    });
  },
};
