/**
 * Auth0 OAuth client using expo-auth-session.
 *
 * Why expo-auth-session and not react-native-auth0:
 *   react-native-auth0 needs native iOS/Android modules linked — won't run in
 *   Expo Go. expo-auth-session uses the system browser, works in Expo Go today,
 *   and gives you the same Auth0 universal login. Same backend verification,
 *   no native code.
 *
 * The redirect URI must match an Allowed Callback URL in your Auth0
 * Application settings. In Expo Go the URI includes the dev-server URL and
 * looks unpredictable; we log it on first sign-in so you can paste it into
 * Auth0 once.
 */
import Constants from "expo-constants";
import * as AuthSession from "expo-auth-session";

// These values come from your Auth0 tenant.
// Tenant: dev-jkck6gr70cocfwfa.us.auth0.com
// Application: Virtual Stylist Mobile (Native)
// API audience: virtual-stylist-api
const AUTH0_DOMAIN = "dev-jkck6gr70cocfwfa.us.auth0.com";
const AUTH0_CLIENT_ID = "xjLQ1bTmcBDPM95SJpx8N0yz3aoB7cBj";
const AUTH0_AUDIENCE = "virtual-stylist-api";

export const auth0Discovery: AuthSession.DiscoveryDocument = {
  authorizationEndpoint: `https://${AUTH0_DOMAIN}/authorize`,
  tokenEndpoint: `https://${AUTH0_DOMAIN}/oauth/token`,
  revocationEndpoint: `https://${AUTH0_DOMAIN}/oauth/revoke`,
  userInfoEndpoint: `https://${AUTH0_DOMAIN}/userinfo`,
};

export function buildRedirectUri(): string {
  // In Expo Go, returns something like `exp+virtual-stylist://expo-development-client/...`.
  // In a standalone build, returns `virtualstylist://auth/callback` matching the
  // app.json `scheme`. Either way, the EXACT string must be in your Auth0
  // Application's Allowed Callback URLs.
  return AuthSession.makeRedirectUri({
    scheme: "virtualstylist",
    path: "auth/callback",
  });
}

export const AUTH0_CONFIG: AuthSession.AuthRequestConfig = {
  clientId: AUTH0_CLIENT_ID,
  responseType: AuthSession.ResponseType.Code,
  scopes: ["openid", "profile", "email", "offline_access"],
  redirectUri: buildRedirectUri(),
  usePKCE: true,
  extraParams: {
    // Tells Auth0 to issue an access_token whose `aud` matches the API.
    // Without this you'd get an opaque /userinfo token only.
    audience: AUTH0_AUDIENCE,
  },
};

export interface Auth0TokenSet {
  accessToken: string;
  idToken?: string;
  refreshToken?: string;
  expiresAt: number; // epoch seconds
  sub: string;
  email?: string;
  name?: string;
}

/**
 * Decode the unverified JWT payload to pull out `sub` / `email`. The backend
 * does the cryptographic verification — this is just for displaying the user's
 * name in the UI.
 */
function decodeJwt(token: string): Record<string, unknown> {
  const parts = token.split(".");
  if (parts.length !== 3 || !parts[1]) return {};
  try {
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    // Pad to length multiple of 4
    const padded = payload + "===".slice((payload.length + 3) % 4);
    const raw = globalThis.atob ? globalThis.atob(padded) : "";
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

/**
 * Exchange the authorization code for tokens.
 */
export async function exchangeCode(
  code: string,
  codeVerifier: string,
): Promise<Auth0TokenSet> {
  const tokens = await AuthSession.exchangeCodeAsync(
    {
      clientId: AUTH0_CLIENT_ID,
      code,
      redirectUri: buildRedirectUri(),
      extraParams: { code_verifier: codeVerifier },
    },
    auth0Discovery,
  );
  if (!tokens.accessToken) throw new Error("Auth0 returned no access_token");
  const claims = decodeJwt(tokens.accessToken);
  const idClaims = tokens.idToken ? decodeJwt(tokens.idToken) : {};
  return {
    accessToken: tokens.accessToken,
    idToken: tokens.idToken,
    refreshToken: tokens.refreshToken,
    expiresAt: Math.floor(Date.now() / 1000) + (tokens.expiresIn ?? 3600),
    sub: String(claims.sub ?? idClaims.sub ?? ""),
    email: (idClaims.email as string | undefined) ?? (claims.email as string | undefined),
    name:
      (idClaims.name as string | undefined) ??
      (idClaims.nickname as string | undefined) ??
      ((idClaims.email as string | undefined)?.split("@")[0]) ??
      "Signed-in user",
  };
}

// Silence unused-import warning for Constants (kept for forwards-compat with
// runtime detection — Expo Go vs Dev Client may need different schemes later).
export const _runtimeOwnership = Constants.appOwnership;
