# Deployment & Secrets

This is the secrets and infrastructure checklist for going from local dev to a
production deploy. Nothing here belongs in git — `.env.production.example`
documents the shape, real values live in Secret Manager / GitHub / EAS.

## 1. GitHub Actions secrets

Set in repo Settings → Secrets and variables → Actions.

| Secret | Used for |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | OIDC-based auth from Actions to GCP (no static keys) |
| `GCP_SERVICE_ACCOUNT` | The deploy SA email |
| `ANTHROPIC_API_KEY` | Integration tests against the real stylist on `main` only |
| `OPENWEATHER_API_KEY` | Integration tests |
| `EXPO_TOKEN` | EAS Build + Submit |
| `APP_STORE_CONNECT_API_KEY_BASE64` | TestFlight submit |
| `APP_STORE_CONNECT_API_KEY_ID` | TestFlight submit |
| `APP_STORE_CONNECT_ISSUER_ID` | TestFlight submit |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` | Play Internal Testing submit |

CI only needs read-level Anthropic / OpenWeather keys — separate keys from
production. Rotate quarterly.

## 2. Google Cloud — one-time setup

```bash
gcloud projects create virtual-stylist-prod
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  storage.googleapis.com aiplatform.googleapis.com secretmanager.googleapis.com \
  redis.googleapis.com cloudbuild.googleapis.com

# Postgres 16 with pgvector available via the `cloudsql.pg_extensions` flag
gcloud sql instances create stylist-pg --database-version=POSTGRES_16 \
  --tier=db-custom-2-8192 --region=us-central1 \
  --database-flags=cloudsql.enable_pgvector=on

# Memorystore Redis
gcloud redis instances create stylist-redis --size=1 --region=us-central1

# GCS bucket with CMEK
gcloud storage buckets create gs://virtual-stylist-prod \
  --location=us-central1 --uniform-bucket-level-access \
  --default-encryption-key=projects/.../cryptoKeys/stylist-bucket-key

# Service accounts
gcloud iam service-accounts create stylist-api-sa
gcloud projects add-iam-policy-binding virtual-stylist-prod \
  --member="serviceAccount:stylist-api-sa@..." \
  --role=roles/cloudsql.client
gcloud projects add-iam-policy-binding virtual-stylist-prod \
  --member="serviceAccount:stylist-api-sa@..." \
  --role=roles/storage.objectAdmin
```

## 3. Cloud Run service

```bash
gcloud run deploy stylist-api \
  --image=us-central1-docker.pkg.dev/virtual-stylist-prod/stylist/api:$SHA \
  --region=us-central1 \
  --service-account=stylist-api-sa@... \
  --add-cloudsql-instances=virtual-stylist-prod:us-central1:stylist-pg \
  --set-secrets=ANTHROPIC_API_KEY=anthropic-key:latest,\
SECRET_KEY=app-secret:latest,\
OPENWEATHER_API_KEY=openweather-key:latest \
  --set-env-vars=ENVIRONMENT=production,\
DATABASE_URL=postgresql+asyncpg://stylist:...@/virtual_stylist?host=/cloudsql/virtual-stylist-prod:us-central1:stylist-pg,\
STORAGE_BACKEND=gcs,GCS_BUCKET=virtual-stylist-prod,\
AUTH_ISSUER=https://auth.virtualstylist.com/,\
AUTH_AUDIENCE=virtual-stylist-api,\
AUTH_JWKS_URL=https://auth.virtualstylist.com/.well-known/jwks.json,\
DEV_AUTH_BYPASS=false,MODEL_GATEWAY_BACKEND=anthropic
```

A second Cloud Run service runs the `arq` worker against the same env.

## 4. EAS (mobile)

```bash
eas init
eas secret:create --scope project --name EXPO_PUBLIC_API_URL --value https://api.virtualstylist.com
eas build --platform all --profile production
eas submit --platform ios --latest
eas submit --platform android --latest
```

## 5. Auth0 / Clerk

- Create a tenant per environment (`stylist-dev`, `stylist-prod`).
- Enable passkeys + email magic link; turn off password sign-up.
- Configure a **Guardian Consent** action that fires before account creation
  when the email indicates a minor-flagged signup. (Hook to your COPPA flow.)
- Add `https://api.virtualstylist.com` as an audience; copy the JWKS URL into
  `AUTH_JWKS_URL`.

### Server-side verification — already wired

`services/api/app/core/auth.py` verifies tokens against the configured JWKS
once `DEV_AUTH_BYPASS=false`. Behaviour:

1. Fetches JWKS on first request, caches it for 1 hour.
2. Validates RS256 signature, `iss`, `aud`, and `exp` on every call.
3. Maps `sub` → `users.auth_provider_id`, auto-provisions on first sign-in.
4. If a user with the same `email` already exists (e.g. account linking after
   switching SSO providers), the row is linked instead of duplicated.

To roll out:

1. Create the Auth0 tenant + API + Application above.
2. Set in production env:
   ```
   AUTH_ISSUER=https://your-tenant.us.auth0.com/
   AUTH_AUDIENCE=virtual-stylist-api
   AUTH_JWKS_URL=https://your-tenant.us.auth0.com/.well-known/jwks.json
   DEV_AUTH_BYPASS=false
   ```
3. Smoke-test by running `tests/test_auth.py` against the live tenant
   (replace the patched JWKS fetcher with the real URL).

### Mobile-side integration

The mobile app currently uses a deterministic-hash dev sign-in. For production,
swap `apps/mobile/src/state/auth.ts` with `react-native-auth0` (or `@clerk/clerk-expo`):

```ts
import { Auth0Provider, useAuth0 } from "react-native-auth0";
// devUserId → accessToken; send via Authorization: Bearer
```

`apps/mobile/src/api/client.ts` already supports `Authorization` headers — just
replace the `X-Dev-User-Id` injection with the real bearer token.

## 6. Pre-launch gates

- [ ] COPPA review signed off by counsel.
- [ ] Privacy policy + ToS published at virtualstylist.com.
- [ ] Anthropic + OpenWeather rate limits adequate for projected DAU.
- [ ] Synthetic outfit-generation probe alerts page on-call.
- [ ] Cost dashboard from the model gateway shows healthy per-request cost.
- [ ] Crash-free sessions ≥99.5% in the beta cohort.
