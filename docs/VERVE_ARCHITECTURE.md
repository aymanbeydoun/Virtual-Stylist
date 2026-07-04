# Project Verve — Core Architecture & Moats

Architecture blueprint for the four proprietary pillars of STaiLE ME's
next-generation styling engine. Pillar 3 (ThemeEngine) is **implemented** in
`apps/mobile` today; Pillars 1, 2 and 4 are specified here to production depth
so implementation is a build-out, not a redesign.

> **Runtime reality check.** The mobile app currently runs in Expo Go, which
> cannot load custom native modules. Pillars 2 and 4 (HealthKit / on-device
> SLM) require an **EAS development build** (`eas build --profile development`)
> — same codebase, one extra build step. Pillar 1 lives entirely in the
> existing FastAPI backend (`services/api`), no native code needed.

---

## Pillar 1 — The Temporal Social Graph (Outfit Memory Engine)

**Moat:** the stylist remembers not just *what you wore*, but *who saw it*,
and refuses to repeat a look in front of the same audience.

### 1.1 Schema (PostgreSQL — extends `services/api/app/models`)

The existing schema already has `users`, `wardrobe_items`, `outfits`,
`outfit_items`, and `outfit_events`. Verve adds three tables:

```sql
-- People who appear in the user's calendar. Contacts are matched by a stable
-- hash of the attendee's email so we never store raw third-party PII.
CREATE TABLE attendees (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_hash    TEXT NOT NULL,              -- sha256(lower(email) + user salt)
    display_name  TEXT,                       -- user-visible label only
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, email_hash)
);

-- Calendar events ingested from EventKit (iOS) / Calendar Provider (Android).
CREATE TABLE calendar_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    external_id   TEXT NOT NULL,              -- provider event id (dedupe key)
    title         TEXT,
    starts_at     TIMESTAMPTZ NOT NULL,
    ends_at       TIMESTAMPTZ,
    location_hint TEXT,                       -- feeds the occasion classifier
    UNIQUE (user_id, external_id)
);

CREATE TABLE event_attendees (
    event_id      UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    attendee_id   UUID NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, attendee_id)
);

-- The core edge of the temporal graph: outfit O was seen at event E.
-- Written when the user marks an outfit "worn" while a calendar event is
-- active (or explicitly links one).
CREATE TABLE outfit_sightings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outfit_id     UUID NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    event_id      UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (outfit_id, event_id)
);

-- Hot-path indexes: "who saw item X in the last N days" must be one seek.
CREATE INDEX idx_sightings_seen_at   ON outfit_sightings (seen_at);
CREATE INDEX idx_event_attendees_att ON event_attendees (attendee_id, event_id);
CREATE INDEX idx_events_user_time    ON calendar_events (user_id, starts_at);
```

Graph reading: `outfit —seen_at→ event —attended_by→ attendee`. A relational
store wins over a graph DB here: the traversal is always exactly two hops,
bounded by a time window, and joins on covered indexes — no need for Neo4j
operational overhead at this scale.

### 1.2 The audience-repetition penalty

Runs inside `stylist_engine.generate_outfits` scoring, per candidate outfit:

```python
AUDIENCE_WINDOW_DAYS = 30
FULL_PENALTY = 0.55        # exact outfit, same audience → score × 0.45
ITEM_PENALTY_CEIL = 0.30   # shared items cap out at a 30% haircut

async def audience_repetition_penalty(
    db, *, user_id, candidate_item_ids: set[UUID],
    target_event_id: UUID | None,
) -> float:
    """Return a multiplier in [1 - FULL_PENALTY, 1.0] for a candidate outfit."""
    if target_event_id is None:
        return 1.0  # no audience context → no penalty

    # 1. Who will be at the target event?
    audience = await fetch_attendee_ids(db, target_event_id)
    if not audience:
        return 1.0

    # 2. Which wardrobe items has this audience already seen in the window?
    #    One query: sightings ∩ window ∩ audience → outfit_items → item ids,
    #    with per-item overlap = |audience who saw it| / |audience|.
    cutoff = now() - timedelta(days=AUDIENCE_WINDOW_DAYS)
    seen = await db.execute(
        select(OutfitItem.item_id,
               func.count(distinct(EventAttendee.attendee_id)))
        .join(OutfitSighting, OutfitSighting.outfit_id == OutfitItem.outfit_id)
        .join(EventAttendee, EventAttendee.event_id == OutfitSighting.event_id)
        .where(OutfitSighting.seen_at >= cutoff,
               EventAttendee.attendee_id.in_(audience),
               OutfitItem.item_id.in_(candidate_item_ids))
        .group_by(OutfitItem.item_id)
    )
    overlap_by_item = {item_id: n / len(audience) for item_id, n in seen}
    if not overlap_by_item:
        return 1.0

    # 3. Blend: repeating the whole look in front of the same people is much
    #    worse than re-wearing one shared piece.
    coverage = len(overlap_by_item) / len(candidate_item_ids)   # how much of
    depth = sum(overlap_by_item.values()) / len(overlap_by_item) # how many saw
    if coverage >= 0.99:
        return 1.0 - FULL_PENALTY * depth
    return 1.0 - min(ITEM_PENALTY_CEIL, coverage * depth * FULL_PENALTY)
```

Recency decay (optional v2): weight each sighting by
`exp(-days_ago / 14)` before summing, so a look seen 28 days ago barely
penalizes while last Friday's fit is near-blocked.

---

## Pillar 2 — Biometric Context Ingestion

**Moat:** the stylist reads your body's day before styling it.

### 2.1 Ingestion pipeline

| Step | iOS | Android |
|---|---|---|
| Source | HealthKit (`sleepAnalysis`, `activeEnergyBurned`, `stepCount`) | Health Connect (`SleepSession`, `ActiveCaloriesBurned`, `Steps`) |
| RN bridge | `@kingstinct/react-native-healthkit` | `react-native-health-connect` |
| Build requirement | EAS dev build + HealthKit entitlement | EAS dev build + Health Connect permissions |

Raw samples never leave the device. The app reduces them to a tiny normalized
context object and sends **only this** with a styling request:

```json
{
  "biometrics": {
    "sleep_quality": 0.42,        // 0..1 — efficiency × duration/8h, clamped
    "activity_level": "high",      // "low" | "moderate" | "high" (vs 14-day avg)
    "readiness": "recovering"      // derived: sleep < 0.6 → "recovering"
  }
}
```

### 2.2 Deterministic weighting (pre-LLM)

Applied in `stylist_engine` candidate scoring **before** prompting, so the
rule holds even if the LLM ignores instructions:

```python
if biometrics.sleep_quality < 0.60:
    for item in candidates:
        tags = item.tags  # e.g. {"fabric": "soft", "fit": "loose", "vibe": "cozy"}
        boost = 1.0
        if tags.get("fabric") == "soft":  boost *= 1.25
        if tags.get("fit") == "loose":    boost *= 1.20
        if tags.get("vibe") == "cozy":    boost *= 1.15
        if tags.get("fit") == "structured": boost *= 0.85  # blazers on no sleep: no
        item.score *= boost
```

### 2.3 Exact system prompt (biometrics + social graph merged)

The prompt the cloud stylist LLM receives — placeholders in `{braces}`:

```text
You are {ai_name}, the user's personal stylist inside STaiLE ME.

## Today's context (authoritative — do not contradict it)
- Occasion: {occasion_label} at {event_title}, {event_time_local}
- Vibe requested: {vibe_label}
- Weather: {temp_c}°C, {condition}
- Body context: sleep quality {sleep_quality_pct}% ({readiness}),
  activity level {activity_level}

## Audience memory (Temporal Social Graph)
The following attendees of today's event have recently seen these wardrobe
items (item id — last seen — share of audience who saw it):
{seen_items_block}

## Hard rules
1. NEVER build a look where items covering more than half the outfit appear
   in the audience-memory list above. Those people have seen it this month.
2. If sleep quality is below 60%, bias every slot toward fabric:soft,
   fit:loose, vibe:cozy items from the candidate list; do not select
   fit:structured pieces unless the occasion is formal_event.
3. Choose ONLY from the candidate items provided below. Never invent items.
4. Return strict JSON matching the provided schema; no prose outside JSON.

## Candidate items
{candidate_items_json}

## Output schema
{output_schema_json}

In the "rationale" field, speak as {ai_name}: one warm sentence on why the
look fits the day, and if audience memory changed your pick, say so naturally
("nobody at this dinner has seen this one yet") without naming attendees.
```

---

## Pillar 3 — Ambient Dynamic UI (ThemeEngine) — ✅ IMPLEMENTED

- `apps/mobile/src/components/ThemeEngine.tsx` — app-wide canvas; the previous
  gradient stays mounted while the next fades in over it on the UI thread
  (Reanimated `withTiming`, 900 ms cubic ease). No hard cuts, ever.
- `apps/mobile/src/theme/auras.ts` — aura definitions (Dusk, Voltage,
  Boardroom, Wine Hour, Cyber, Arcade), all ink-anchored to `#0A0B0E` so the
  design system's contrast survives every transition.
- `apps/mobile/src/state/aura.ts` — live aura store; set on outfit
  generation (`StyleScreen.onStaileMe`), cleared when the user picks a manual
  backdrop.

v2 hooks (specified, not yet wired): weather tint (drizzle desaturates the
aura 20%), scroll-position parallax via `useAnimatedScrollHandler`, and Skia
mesh gradients (`@shopify/react-native-skia`) once we move to a dev build.

---

## Pillar 4 — Edge-AI Hybrid Pipeline

**Moat:** zero-latency chat, private by construction; the cloud only does
what a phone physically cannot.

### 4.1 Workload routing

```
                        ┌────────────────────────────────────────┐
 user input ──► intent  │ ON-DEVICE (SLM, ~1B params, 4-bit)     │
             classifier │  • chat small-talk & daily check-in    │
             (on-device)│  • outfit edit commands ("swap shoes") │
                        │  • rationale rephrasing                │
                        └───────────────┬────────────────────────┘
                                        │ structured edit ops / escalation
                        ┌───────────────▼────────────────────────┐
                        │ CLOUD GPU (FastAPI model gateway)      │
                        │  • CV tagging + background removal     │
                        │  • IDM-VTON try-on rendering           │
                        │  • full outfit generation w/ social    │
                        │    graph + biometrics prompt (above)   │
                        └────────────────────────────────────────┘
```

The SLM never free-generates outfit changes — it emits a structured op
(`{"op":"swap","slot":"shoes","constraint":"less colorful"}`) that the local
demo engine (today) or cloud engine (later) executes. Chat feels instant; the
catalog stays authoritative.

### 4.2 Tech stack lockdown

| Concern | Decision | Why |
|---|---|---|
| On-device SLM runtime | **`react-native-executorch`** (Software Mansion) | Actively maintained RN bindings for PyTorch ExecuTorch; iOS + Android from one API |
| Model | **Llama 3.2 1B Instruct, 4-bit (SpinQuant)**; fallback Qwen2.5-0.5B for low-RAM Android | Fits < 1.2 GB RAM, ~30-60 tok/s on A17/8 Gen 2 class devices |
| iOS-only alt (v2) | MLX via native module | Apple-silicon speed, but Swift-only — not worth the dual codepath at MVP |
| Escalation LLM (cloud) | Existing `model_gateway.py` provider slot | Already the single point of entry for all providers |
| CV tagging / try-on | Cloud GPU: SigLIP tagging + IDM-VTON | Multi-GB models; never on-device |
| Build system | **EAS dev build** (`expo-dev-client`) | ExecuTorch and HealthKit are native modules — Expo Go cannot load them; EAS keeps the Expo workflow |
| Privacy line | Biometrics reduced on device (§2.1); attendee emails hashed (§1.1); chat history never leaves device unless escalated | The moat doubles as the privacy story |

### 4.3 Latency budget

| Path | Target |
|---|---|
| Chat first token (on-device) | < 150 ms |
| Edit op → canvas update (local engine) | < 100 ms |
| Full generation (cloud, incl. social-graph query) | < 2.5 s |
| Try-on render (cloud, async) | < 8 s, streamed when ready |
