# Auth0 setup — production sign-in

The backend's JWT verifier is already wired (`services/api/app/core/auth.py`).
This guide walks through the Auth0-side setup, the env vars to set, and the
verification CLI to confirm the loop closes before flipping
`DEV_AUTH_BYPASS=false`.

Estimated time: **20 minutes**, no code changes needed.

---

## 1. Create the tenant

1. Go to [auth0.com](https://auth0.com) → **Sign up** (or log in).
2. Pick a tenant name. Convention: `virtual-stylist-dev` and a separate
   `virtual-stylist-prod` later.
3. Region: **EU (Frankfurt)** for GCC users — lowest latency. (US East
   if you'd prefer.)

## 2. Create the API (audience)

Auth0 calls the backend an "API". Each app that signs in requests tokens
*for* this API.

1. Auth0 dashboard → **Applications → APIs → + Create API**.
2. **Name**: `Virtual Stylist API`.
3. **Identifier (audience)**: `virtual-stylist-api`
   — this exact string goes into `AUTH_AUDIENCE` on the backend.
   It does *not* need to be a real URL.
4. **Signing Algorithm**: RS256 (default; the verifier expects RS256).
5. Save.

## 3. Create the Application (mobile client)

1. Auth0 dashboard → **Applications → Applications → + Create Application**.
2. **Name**: `Virtual Stylist iOS / Android`.
3. **Type**: **Native** (not SPA or Regular Web).
4. After creation, on the **Settings** tab:
   - **Allowed Callback URLs**:
     ```
     com.virtualstylist.app://callback,
     com.virtualstylist.app.auth0://your-tenant.us.auth0.com/ios/com.virtualstylist.app/callback,
     com.virtualstylist.app.auth0://your-tenant.us.auth0.com/android/com.virtualstylist.app/callback
     ```
     (Replace `your-tenant.us.auth0.com` with your tenant's domain.)
   - **Allowed Logout URLs**: same as callbacks.
   - **Token Endpoint Authentication Method**: **None** (native apps don't
     keep a client secret).
5. **Connections** tab: enable
   - **Username-Password-Authentication** (turn on **Sign-Up** if you want
     self-service)
   - **google-oauth2** (Sign in with Google)
   - **apple** (Sign in with Apple) — required by App Store review if you
     offer any other social provider on iOS.

## 4. Enable passkeys (optional but recommended)

Auth0 dashboard → **Authentication → Authentication Profile → Identifier
+ Biometrics** → toggle on. New iOS / Android users get passkey sign-up by
default with email magic link as fallback.

## 5. Copy the values into your env

From the Application's Settings tab:
- **Domain** (e.g. `virtual-stylist-prod.eu.auth0.com`)
- **Client ID** (used only by the mobile SDK)

Set in production env (Secret Manager / GitHub Actions / Cloud Run vars):

```bash
AUTH_ISSUER=https://virtual-stylist-prod.eu.auth0.com/   # trailing slash required
AUTH_AUDIENCE=virtual-stylist-api
AUTH_JWKS_URL=https://virtual-stylist-prod.eu.auth0.com/.well-known/jwks.json
DEV_AUTH_BYPASS=false
```

`AUTH_ISSUER` MUST end with `/` — Auth0 issues tokens with that exact `iss`
claim and the verifier compares as a string.

## 6. Verify the loop closes (before flipping the bypass)

The verify-jwks script confirms three things end-to-end:
1. The JWKS URL is reachable from the API host.
2. RS256 verification succeeds on a real token from your tenant.
3. The user provisioning path (DB row created on first sign-in) works.

### 6a. Get a real test token

In the Auth0 dashboard, open your API → **Test** tab. Auth0 generates a
machine-to-machine token signed by your tenant. Copy it.

### 6b. Run the verifier

```bash
cd services/api
uv run python scripts/verify_auth0.py --token "$AUTH0_TEST_TOKEN"
```

You should see:
```
✓ JWKS reachable                 https://...auth0.com/.well-known/jwks.json
✓ Issuer matches                 https://...auth0.com/
✓ Audience matches               virtual-stylist-api
✓ Signature verified (RS256)
✓ exp/iat valid
✓ User row provisioned           id=...
```

If any step fails the script prints the exact mismatch (e.g. issuer
`https://foo.auth0.com` vs configured `https://foo.auth0.com/`).

## 7. Flip the bypass

Once `verify_auth0.py` is green:

```bash
# In production env only — leave dev at DEV_AUTH_BYPASS=true
DEV_AUTH_BYPASS=false
```

Restart the API. From now on every request requires a valid Bearer token.

## 8. Wire the mobile SDK

`apps/mobile/src/state/auth.ts` currently uses a nickname → deterministic
UUID. Swap for `react-native-auth0`:

```bash
cd apps/mobile
pnpm add react-native-auth0
```

```tsx
// App.tsx
import { Auth0Provider } from "react-native-auth0";

export default function App() {
  return (
    <Auth0Provider
      domain="virtual-stylist-prod.eu.auth0.com"
      clientId="<your client id>"
    >
      {/* ...existing tree */}
    </Auth0Provider>
  );
}
```

```tsx
// SignInScreen.tsx
import { useAuth0 } from "react-native-auth0";
const { authorize, getCredentials } = useAuth0();

async function signIn() {
  await authorize({ audience: "virtual-stylist-api" });
  const creds = await getCredentials();
  // Hand the accessToken to your existing auth store; client.ts already
  // supports `Authorization: Bearer <token>` headers.
}
```

`apps/mobile/src/api/client.ts` already prefers `Authorization` over
`X-Dev-User-Id`. The dev-bypass path stays available behind the env var
for local development.

## 9. COPPA consideration

Auth0 has a **Pre-User-Registration Action** that fires before any account
is created. Use it to gate kid sign-ups behind a Guardian consent flow
(see `docs/legal/COPPA.md`).
