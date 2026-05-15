# MVP Roadmap — 4 Phases to a Working iOS + Android Prototype

Goal: a TestFlight + Play Console internal-test build with a real closet → real
outfit → real affiliate click loop, end-to-end, within ~16 weeks.

Each phase ends with a **demoable build** and a **go/no-go gate**.

---

## Phase 1 — Foundations (Weeks 1–3)

**Objective**: Skeleton app + skeleton API + auth, no AI yet.

### Deliverables
- Monorepo bootstrapped (`pnpm` workspaces, `apps/mobile`, `services/api`, `packages/shared-types`).
- Mobile: Expo + RN New Architecture, TypeScript strict, navigation shell with 4 tabs (Closet, Style, Family, You).
- Backend: FastAPI service deployed to Cloud Run with health check, OpenAPI auto-generated, types regenerated into `shared-types` on CI.
- Auth: Auth0 integration (passkey + email magic link), guardian sign-up flow with the kid-consent placeholder screen wired but no kid sub-profiles yet.
- Postgres + pgvector provisioned; Alembic migrations for `users`, `family_members`, `style_profiles`.
- GCS buckets + signed-URL upload endpoint.
- CI/CD: GitHub Actions → EAS preview builds on every PR.

### Go/No-Go Gate
- A new user can sign up, see the empty closet, and the build distributes via TestFlight + Internal Testing.

---

## Phase 2 — The Wardrobe (Weeks 4–7)

**Objective**: Frictionless item ingestion with auto-tagging is the headline.

### Deliverables
- **Mobile**:
  - Camera capture (`react-native-vision-camera`) with on-device resize.
  - Bulk select from camera roll.
  - Closet grid with infinite scroll + category filters.
  - Item detail screen with one-tap tag corrections.
- **Backend**:
  - `POST /wardrobe/items` accepts a signed-URL pointer.
  - Ingest worker (Arq on Redis) runs the pipeline: background removal (SAM 2 / rembg) → category classifier (start with CLIP zero-shot + a small fine-tuned head) → color/pattern extraction → CLIP embedding → write to Postgres.
  - Migrations for `wardrobe_items`, `item_corrections`.
- **Model gateway** v1 (a single internal client wrapping Vertex AI + provider routing rules).
- **Telemetry**: per-stage latency and confidence histograms in dashboards.

### Quality bars
- ≥90% top-1 category accuracy on a 500-item internal eval set.
- p95 ingest latency ≤8s end-to-end (we'll squeeze to 5s in Phase 4).

### Go/No-Go Gate
- A new user can upload 10 photos in under a minute, see them auto-categorized, and correct a tag with one tap.

---

## Phase 3 — The Stylist + Family Mode (Weeks 8–12)

**Objective**: Mood & Move outfit generation + COPPA-safe kid sub-profiles.

### Deliverables
- **Stylist engine**:
  - Context builder pulls weather (OpenWeather, 15-min cache) and recent outfit history.
  - Candidate retrieval via pgvector + hard filters (season, formality, last-worn).
  - LLM stylist call through the model gateway, forced-JSON output schema.
  - Validator + one-shot re-prompt on rule violations.
  - Server-side flat-lay compositor (Skia in a Node worker) producing a cached PNG per outfit.
  - Endpoint: `POST /stylist/generate` returning 2–3 outfits with rationales and thumbnails.
- **Mobile**:
  - "Style me" screen: destination chips + mood chips + an optional notes field.
  - Outfit carousel with swipe to skip, tap to save, "Wear today" CTA → writes an `outfit_events` row.
- **Family ecosystem**:
  - Guardian creates a kid sub-profile (full COPPA consent flow: card check or signed ID).
  - Kid-mode UI variant (larger touch, mascot, "missions" framing).
  - Migrations for `family_members`, `kid_consents`, `outfits`, `outfit_items`, `outfit_events`.
  - Row-level security policies enforced and tested.

### Quality bars
- p95 outfit generation ≤4s.
- 100% of generated outfits pass the rule validator on the first or second try.
- Manual COPPA-compliance review checklist signed off by counsel before kid mode ships to TestFlight.

### Go/No-Go Gate
- A guardian can create a kid profile, both can upload items, both can generate a styled outfit, and a third-party COPPA audit checklist passes.

---

## Phase 4 — Monetization, Polish, Soft Launch (Weeks 13–16)

**Objective**: Closet gap analysis + affiliate revenue loop + production-grade polish.

### Deliverables
- **Gap analysis**:
  - Nightly job scoring each user's closet against capsule reference matrices per persona archetype.
  - Surface 2–3 gaps in a "Closet insights" tab.
- **Affiliate integration**:
  - Adapters for Brands For Less and Ounass (Amazon as fallback).
  - Suggestion fetcher with 24h cache, locale + size filtering.
  - Signed affiliate-attribution tokens on every outgoing deeplink.
  - Affiliate suggestions **hidden** on kid sub-profiles unless guardian opts in.
- **Polish**:
  - Reanimated 3 transitions on outfit swipe.
  - Empty / error / offline states across all screens.
  - Accessibility audit (VoiceOver, TalkBack, dynamic type, contrast).
  - Localization scaffolding (en, ar — given the BFL/Ounass markets).
  - Push notifications: "3 new outfit ideas for today's weather."
- **Production-grade observability**: synthetic outfit-generation probe every 5 minutes paging on-call.
- **Soft launch**:
  - TestFlight external beta + Play Console open testing track in 2–3 markets (UAE, Saudi, US).
  - Feature flags (GrowthBook) for the gap-analysis surface so we can A/B placement.

### Quality bars
- Crash-free sessions ≥99.5% in the beta cohort.
- Affiliate click-through ≥3% on the gap-insights surface (early signal of monetization fit).
- D7 retention ≥25% in the beta cohort.

### Go/No-Go Gate (= 1.0 Launch Readiness)
- All P0 bugs closed.
- Legal sign-off on COPPA + privacy policy + affiliate disclosures.
- Cost per active user modeled and within the unit-economics threshold.

---

## Cross-phase tracks (run continuously)

| Track | Owner | Notes |
|---|---|---|
| **Eval datasets** | ML | 500 → 5,000 internal-labelled items across men/women/kids by end of Phase 3. |
| **Privacy & compliance** | Legal + Eng | COPPA, GDPR, UAE PDPL reviews staged before kid mode and before soft launch. |
| **Design system** | Design | Shared tokens + components in `packages/ui` from week 2 onward; kid-mode variant lands in Phase 3. |
| **Cost modeling** | Eng + Finance | Per-request cost dashboard from the model gateway; weekly review starting Phase 2. |

## What we explicitly defer to v2

Social feed, AR try-on, P2P resale, custom tailoring, brand-sponsored editorial.
Not because they're bad — because they distract from proving the wardrobe →
stylist → affiliate loop, which is the entire valuation thesis.
