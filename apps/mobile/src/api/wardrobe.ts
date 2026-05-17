import { api } from "@/api/client";
import type { OwnerKind, UploadUrlResponse, WardrobeItem } from "@/api/types";

const baseUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Upload a local file URI (file://... from ImagePicker) to the given upload URL.
 *
 * The `fetch(uri) → .blob()` pattern is unreliable in React Native: on iOS, the
 * resulting Blob is often empty, and on Android the polyfill struggles with
 * Photos asset URIs. RN's FormData accepts a `{ uri, name, type }` descriptor
 * directly and handles the file streaming natively. That's the canonical
 * pattern.
 *
 * For dev (relative URL → local-disk storage) we always go multipart.
 * For prod GCS signed URLs (absolute URL with auth in querystring) we'd need
 * raw-body PUT — also handled below.
 */
async function uploadFileUri(
  uploadUrl: string,
  uri: string,
  contentType: string,
): Promise<void> {
  const isAbsolute = uploadUrl.startsWith("http");
  const target = isAbsolute ? uploadUrl : `${baseUrl}${uploadUrl}`;

  if (isAbsolute) {
    // GCS-style signed PUT: raw body. Read the file as bytes via fetch (works
    // for file:// URIs even when .blob() doesn't, because we're piping it
    // straight to the upload).
    const fileResp = await fetch(uri);
    const body = await fileResp.arrayBuffer();
    const resp = await fetch(target, {
      method: "PUT",
      body,
      headers: { "Content-Type": contentType },
    });
    if (!resp.ok) throw new Error(`upload failed: ${resp.status}`);
    return;
  }

  // Local dev endpoint expects multipart. RN's FormData accepts the file
  // descriptor object directly — no Blob conversion needed.
  const formData = new FormData();
  const filename = uri.split("/").pop() || "upload.jpg";
  // The cast is required because TS lib.dom typings don't model RN's
  // FileLike-as-FormData-value extension.
  formData.append("file", {
    uri,
    name: filename,
    type: contentType,
  } as unknown as Blob);

  const resp = await fetch(target, { method: "PUT", body: formData });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`upload failed: ${resp.status} ${text.slice(0, 200)}`);
  }
}

export const wardrobeApi = {
  async createUploadUrl(contentType: string, owner: { kind: OwnerKind; id?: string }) {
    return api<UploadUrlResponse>("/wardrobe/upload-url", {
      method: "POST",
      json: { content_type: contentType, owner_kind: owner.kind, owner_id: owner.id },
    });
  },

  uploadFileUri,

  /** @deprecated kept for back-compat; new code should use uploadFileUri */
  async uploadBytes(uploadUrl: string, bytes: Blob, contentType: string) {
    const isAbsolute = uploadUrl.startsWith("http");
    const target = isAbsolute ? uploadUrl : `${baseUrl}${uploadUrl}`;

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

  async retry(itemId: string) {
    return api<WardrobeItem>(`/wardrobe/items/${itemId}/retry`, { method: "POST" });
  },

  async remove(itemId: string) {
    return api<void>(`/wardrobe/items/${itemId}`, { method: "DELETE" });
  },
};
