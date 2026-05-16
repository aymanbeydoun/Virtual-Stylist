import { create } from "zustand";

interface AuthState {
  devUserId: string | null;
  displayName: string | null;
  signIn: (rawId: string) => void;
  signOut: () => void;
}

/**
 * Derive a deterministic UUIDv5-like string from a free-text dev ID.
 * The backend's X-Dev-User-Id header must parse as a UUID, but the SignIn
 * screen lets you type any nickname. We hash the nickname into a stable
 * UUID so the same name always resolves to the same dev user row.
 */
function nicknameToUuid(nickname: string): string {
  // Simple FNV-1a 64-bit → 16 bytes → UUID-shaped string. Deterministic across runs.
  const FNV_PRIME = 0x100000001b3n;
  const FNV_OFFSET = 0xcbf29ce484222325n;
  let h = FNV_OFFSET;
  for (let i = 0; i < nickname.length; i++) {
    h ^= BigInt(nickname.charCodeAt(i));
    h = (h * FNV_PRIME) & 0xffffffffffffffffn;
  }
  // Mix h with itself to fill 32 hex chars deterministically.
  const hex = h.toString(16).padStart(16, "0");
  const mix = ((h * FNV_PRIME) ^ FNV_OFFSET).toString(16).padStart(16, "0").slice(0, 16);
  const u = (hex + mix).slice(0, 32);
  return `${u.slice(0, 8)}-${u.slice(8, 12)}-${u.slice(12, 16)}-${u.slice(16, 20)}-${u.slice(20, 32)}`;
}

export const useAuth = create<AuthState>((set) => ({
  devUserId: null,
  displayName: null,
  signIn: (rawId) => {
    const trimmed = rawId.trim();
    if (!trimmed) return;
    const uuid = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/
      .test(trimmed)
      ? trimmed
      : nicknameToUuid(trimmed.toLowerCase());
    set({ devUserId: uuid, displayName: trimmed });
  },
  signOut: () => set({ devUserId: null, displayName: null }),
}));
