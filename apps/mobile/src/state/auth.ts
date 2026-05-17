import { create } from "zustand";

import type { Auth0TokenSet } from "@/api/auth0";

/**
 * Auth state supports two modes during the transition to real Auth0:
 *
 *   - "auth0": real Auth0 session. We have an accessToken (sent as Bearer),
 *     plus sub/email/name from the ID token claims. Backend trusts the token
 *     cryptographically. Production path.
 *
 *   - "dev": legacy nickname → deterministic-UUID dev sign-in. Sends
 *     X-Dev-User-Id header. Backend trusts it only when DEV_AUTH_BYPASS=true.
 *     Convenient for local iteration; gone once we flip the bypass.
 *
 * Mobile API client picks the right header based on `mode`.
 */
export type AuthSession =
  | {
      mode: "auth0";
      accessToken: string;
      idToken?: string;
      refreshToken?: string;
      expiresAt: number;
      sub: string;
      email?: string;
      displayName: string;
    }
  | {
      mode: "dev";
      devUserId: string;
      displayName: string;
    };

interface AuthState {
  session: AuthSession | null;
  // Kept for back-compat with screens that already read `devUserId` / `displayName`.
  devUserId: string | null;
  displayName: string | null;
  signInWithAuth0: (tokens: Auth0TokenSet) => void;
  signInAsDev: (rawId: string) => void;
  signOut: () => void;
}

/**
 * Derive a deterministic UUIDv5-like string from a free-text dev ID so the
 * backend's X-Dev-User-Id header is always valid. Same name → same dev row.
 */
function nicknameToUuid(nickname: string): string {
  const FNV_PRIME = 0x100000001b3n;
  const FNV_OFFSET = 0xcbf29ce484222325n;
  let h = FNV_OFFSET;
  for (let i = 0; i < nickname.length; i++) {
    h ^= BigInt(nickname.charCodeAt(i));
    h = (h * FNV_PRIME) & 0xffffffffffffffffn;
  }
  const hex = h.toString(16).padStart(16, "0");
  const mix = ((h * FNV_PRIME) ^ FNV_OFFSET).toString(16).padStart(16, "0").slice(0, 16);
  const u = (hex + mix).slice(0, 32);
  return `${u.slice(0, 8)}-${u.slice(8, 12)}-${u.slice(12, 16)}-${u.slice(16, 20)}-${u.slice(20, 32)}`;
}

export const useAuth = create<AuthState>((set) => ({
  session: null,
  devUserId: null,
  displayName: null,

  signInWithAuth0: (tokens) => {
    const session: AuthSession = {
      mode: "auth0",
      accessToken: tokens.accessToken,
      idToken: tokens.idToken,
      refreshToken: tokens.refreshToken,
      expiresAt: tokens.expiresAt,
      sub: tokens.sub,
      email: tokens.email,
      displayName: tokens.name ?? tokens.email ?? "Signed in",
    };
    set({
      session,
      devUserId: null,
      displayName: session.displayName,
    });
  },

  signInAsDev: (rawId) => {
    const trimmed = rawId.trim();
    if (!trimmed) return;
    const uuid = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/
      .test(trimmed)
      ? trimmed
      : nicknameToUuid(trimmed.toLowerCase());
    const session: AuthSession = { mode: "dev", devUserId: uuid, displayName: trimmed };
    set({ session, devUserId: uuid, displayName: trimmed });
  },

  signOut: () => set({ session: null, devUserId: null, displayName: null }),
}));
