# System Architecture — Virtual Stylist

## 1. Tech Stack Recommendation

### 1.1 Frontend — **React Native (with Expo + the New Architecture)**

**Why React Native over Flutter:**

| Criterion | React Native | Flutter | Pick |
|---|---|---|---|
| Hiring pool & ecosystem maturity for fast-scaling teams | Very large (JS/TS) | Smaller (Dart) | **RN** |
| Native module ecosystem for camera, ML, in-app payments, affiliate SDKs | Mature (vision-camera, ML Kit bridges, RevenueCat) | Mature but smaller third-party set | **RN** |
| Web/admin reuse (shared component logic for an ops dashboard) | High (React) | Low (Flutter web is workable, not great for dashboards) | **RN** |
| OTA updates for rapid iteration | Native via EAS Update | Possible but less standard | **RN** |
| Performance for image-heavy UI | Excellent on the New Architecture (Fabric + TurboModules) | Excellent | tie |

Supporting choices:
- **TypeScript** strict mode across the entire app.
- **Expo + EAS Build** for managed iOS/Android builds, OTA updates, and config-driven environments.
- **State**: TanStack Query for server state + Zustand for local UI state. (No Redux — premature complexity.)
- **Navigation**: React Navigation (native stack).
- **Image pipeline**: `react-native-vision-camera` for capture, `expo-image` for caching, on-device thumbnail downscale before upload.
- **Animations**: Reanimated 3 + Skia for the kid-mode mascot and outfit-swipe transitions.

### 1.2 Backend — **Python / FastAPI + Node worker for image ops**

- **API layer**: FastAPI (async, OpenAPI-first, type-safe with Pydantic). Single primary service to start; split by domain (`wardrobe`, `stylist`, `family`, `commerce`) only when team size demands it.
- **Auth**: Auth0 or Clerk (faster than rolling our own; supports passkeys and the parental-consent flows we'll need for COPPA out of the box).
- **Workers**: Celery (or, simpler, **Arq** on Redis) for asynchronous CV jobs. A separate Node worker handles `sharp`-based image preprocessing where Python's PIL is slower.
- **Realtime**: Server-sent events for "outfit generating…" progress; full WebSocket only if/when we add multi-user closet sharing.

### 1.3 Data Layer

- **Primary OLTP**: **PostgreSQL** (managed — Cloud SQL or RDS). Strong relational fit for family/wardrobe/outfit graphs.
- **Vector store**: **pgvector** extension in the same Postgres for clothing embeddings (avoids running a separate Pinecone/Weaviate until scale demands it). Migrate to a dedicated vector DB at >10M items.
- **Object storage**: **Google Cloud Storage** or **S3** for raw photos, cutouts, and thumbnails. Signed URLs only — never public buckets.
- **Cache**: Redis (Memorystore / ElastiCache) for sessions, weather lookups, and rate limits.
- **Analytics warehouse**: BigQuery or Snowflake via CDC from Postgres (Phase 3).

### 1.4 Cloud — **GCP, with cross-cloud guardrails**

Rationale: Vertex AI gives us a clean path to managed Gemini multimodal calls and serverless GPU inference; Cloud Run scales the API to zero between launch-window traffic spikes. AWS is the fallback for any service GCP lacks parity on. Avoid lock-in by routing all model calls through an internal "model gateway" service so we can swap providers (OpenAI, Anthropic, self-hosted) per task type.

| Concern | Service |
|---|---|
| API hosting | Cloud Run (autoscaling, scale-to-zero) |
| GPU inference | Vertex AI endpoints (background removal, classifier) |
| Object storage | Cloud Storage |
| Queue | Pub/Sub |
| Secrets | Secret Manager |
| CDN | Cloud CDN in front of GCS |
| Observability | Cloud Logging + OpenTelemetry → Grafana Cloud |

### 1.5 DevEx & Quality Gates

- Monorepo with `pnpm` workspaces: `apps/mobile`, `services/api`, `packages/shared-types`.
- CI on GitHub Actions: typecheck, lint, unit + integration tests, EAS preview builds on every PR.
- Feature flags via **GrowthBook** (self-hosted) so kid-mode and affiliate placements can be toggled per cohort.

---

## 2. AI Pipeline Design

The AI surface area is two pipelines: **Item ingestion** (CV-heavy) and
**Outfit generation** (LLM-orchestrated, CV-augmented).

### 2.1 Item Ingestion Pipeline

```
[Mobile capture] ──► [Pre-upload resize on device]
       │
       ▼
[POST /wardrobe/items (signed URL)] ──► [GCS: raw/]
       │
       ▼
[Pub/Sub: item.uploaded] ──► [Ingest Worker]
       │
       ├──► (1) Background removal     (SAM 2 or rembg, Vertex endpoint)
       ├──► (2) Category classifier    (fine-tuned ViT on DeepFashion + Fashionpedia + internal labels)
       ├──► (3) Color extraction       (k-means in LAB space → named palette)
       ├──► (4) Pattern detector       (lightweight CNN: solid / stripe / floral / graphic / plaid)
       ├──► (5) Embedding              (CLIP ViT-L/14 → 768-d vector, stored in pgvector)
       └──► (6) Seasonality inference  (rules over fabric guess + category + sleeve length)
       │
       ▼
[Write item record + tags + embedding to Postgres]
       │
       ▼
[Push notification: "3 items added to your closet"]
```

Key design choices:
- **CLIP embeddings are the universal currency.** Any new model can reference items by vector without re-tagging.
- **Confidence thresholds**: anything below 0.7 confidence flips a "needs review" flag — the user sees the tag with a subtle edit icon, never a blocking modal.
- **Cold start cost control**: classification and pattern detection run on the same container/GPU in one batched call.
- **Privacy**: raw photos for kids' items get an extra `coppa=true` flag that excludes them from any model retraining pipeline.

### 2.2 Outfit Generation Pipeline

```
User taps "Style me" → POST /stylist/generate
   { destination, mood, optional_notes }
              │
              ▼
[Context Builder]
   - Pull weather (cached, 15-min TTL) for user's lat/lon
   - Pull user's recent outfit log (last 14 days)
   - Pull closet snapshot (categories + counts + embeddings)
              │
              ▼
[Candidate Retrieval]
   - Vector search: top-K items per slot (top, bottom, shoes, accessory)
     scored against (mood-vector + destination-vector + weather-rules)
   - Hard filters: seasonality, formality band, "last worn within 3 days" exclusion
              │
              ▼
[LLM Stylist  — multimodal call to Gemini 2.x or Claude]
   Input:
     - System prompt encoding style rules (color theory, occasion formality, kid-mode safety)
     - Structured JSON of candidate items (id, category, color, pattern, formality)
     - User context (destination, mood, weather)
   Output (forced JSON schema):
     {
       outfits: [
         { items: [item_id…], rationale: "...", confidence: 0.0-1.0 }
       ]  // 2 or 3 entries
     }
              │
              ▼
[Validator]
   - Re-check each outfit against hard rules
     (no two tops, shoes present, weather-appropriate)
   - If validation fails, re-prompt once with the specific violation
              │
              ▼
[Compositor]
   - Layer cutouts onto a flat-lay canvas (server-side Skia or a lightweight
     templated render) → cached thumbnail per outfit
              │
              ▼
[Response to mobile] — outfits + rationales + thumbnails
              │
              ▼
[Log to outfit_history for retrieval + retraining]
```

Provider routing through the **model gateway**:

| Task | Default model | Fallback | Why |
|---|---|---|---|
| Background removal | SAM 2 (Vertex endpoint) | `rembg` self-hosted | Quality + speed |
| Category & attribute | Fine-tuned ViT | CLIP zero-shot prompt | Cost control |
| Stylist reasoning | `claude-sonnet-4-6` | `gemini-2.x-pro` | Best instruction-following on structured outputs |
| Kid-mode stylist | `claude-haiku-4-5` | n/a | Faster, cheaper, simpler outputs |

(All model IDs are configurable; the gateway exposes a single `/infer` API to callers.)

### 2.3 Gap Analysis (background job, daily)

- For each active user, compute closet vector centroid + coverage matrix
  across (category × formality × season).
- Compare to a curated "capsule reference" matrix per persona.
- Top 3 missing cells → query affiliate APIs filtered to user's size, budget
  band, and locale → cache for 24h.

---

## 3. Service Boundaries (MVP)

A single FastAPI service with clear module boundaries. We do **not** start with
microservices — modular monolith is faster to ship and easier to refactor.

```
/services/api/
  app/
    auth/           # Auth0 webhook, family/guardian linking
    wardrobe/       # Items, tags, cutouts
    stylist/        # Outfit generation orchestration
    family/         # Sub-profiles, COPPA consent, kid-mode toggles
    commerce/       # Affiliate adapters (Brands For Less, Ounass, Amazon)
    gap_analysis/   # Background scoring job
    model_gateway/  # Single interface to CV + LLM providers
    weather/        # Cached external-API client
    common/         # Shared models, error types, telemetry
```

Each module owns its DB tables and exposes only typed Python interfaces to peers.
When we split into services later, the seams are already drawn.

---

## 4. Security & Compliance Posture

- **At rest**: Postgres encrypted (CMEK), GCS bucket encryption with customer-managed keys for kid data.
- **In transit**: TLS 1.3 only; certificate pinning on mobile for the API host.
- **AuthN/AuthZ**: short-lived JWTs (15 min) + refresh tokens; row-level security in Postgres so a guardian can only ever read their own family tree.
- **COPPA**: separate `kid_consent` table with consent timestamp, method (credit-card check, signed ID, or knowledge-based), and the guardian who granted it. Cron job purges kid data 30 days after a deletion request.
- **PII minimization**: store no precise lat/lon — round to the nearest 5km for weather lookups.
- **Audit**: every kid-profile access is logged immutably (append-only table + BigQuery export).

---

## 5. Observability

- Structured JSON logs via `structlog`, OTel traces from FastAPI middleware.
- Synthetic checks: a probe account regenerates an outfit every 5 minutes; failure pages on-call.
- ML-specific dashboards: tag-correction rate by category, outfit acceptance rate by mood, gateway latency per provider.
