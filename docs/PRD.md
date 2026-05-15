# Product Requirements Document — Virtual Stylist

## 1. Problem & Opportunity

Every morning, billions of people spend 10–20 minutes deciding what to wear and
still feel under-styled. Existing wardrobe apps fail because they demand
**manual data entry** (typing brand, color, category for every item). The
opportunity: collapse closet onboarding to **photo → tagged item in <5 seconds**
using computer vision, then layer a multimodal LLM stylist on top.

Target valuation thesis: a frictionless wardrobe layer becomes the default
"shop the look" surface for affiliate commerce — a 2–4% take rate on a
~$1.7T global apparel market is the path to a $1B+ outcome.

## 2. Target Users

| Persona | Primary need | Key feature |
|---|---|---|
| **Women (18–55)** | Outfit variety, occasion-matching, jewelry/shoe pairing | Mood & Move engine |
| **Men (22–55)** | Speed and simplicity, never look mismatched | One-tap "What works today?" |
| **Kids (6–12, via Guardian)** | Independence picking school/weekend outfits | Gamified kid UI |
| **Parents (Guardians)** | Manage kid sub-profiles, save morning time | Family ecosystem + COPPA-safe controls |

## 3. Core Features

### 3.1 Frictionless Digital Wardrobe

- User snaps or uploads a photo of an apparel item, shoe, hat, jewelry, or accessory.
- System auto-runs:
  - **Background removal** (clean cutout for outfit composition).
  - **Category classification** (e.g., "Women's stiletto," "Men's fedora," "Kid's graphic tee").
  - **Attribute tagging**: dominant color(s), pattern (solid / stripe / floral / graphic), material guess, estimated seasonality, formality score.
- **Zero required manual entry.** Users may correct tags, but the default flow is one tap → saved.
- Bulk upload from camera roll with batched inference.

**Acceptance criteria**
- ≥90% top-1 category accuracy on internal eval set across men/women/kids categories.
- ≤5 seconds end-to-end per item on a mid-range device + warm backend.
- Manual correction is one tap and feeds a retraining queue.

### 3.2 The "Mood & Move" Styling Engine

- Inputs: **Destination** (Office, Date, Brunch, Gym, Playground, School, Travel, Formal Event) + **Mood** (Confident, Cozy, Edgy, Playful, Minimal, Romantic) + optional notes.
- Implicit inputs (auto-collected): current weather at user's location, time of day, recent outfit history (avoid repeats), color theory rules.
- Output: **2–3 complete outfits**, each including top, bottom (or dress), outerwear if needed, shoes, and at least one accessory (jewelry / belt / hat / bag) where appropriate, all drawn from the user's closet.
- Each outfit comes with a 1–2 sentence "why this works" caption.

**Acceptance criteria**
- p95 latency to first outfit ≤4s.
- Outfits respect weather (no wool coats at 30°C, no sandals in rain).
- No item appears in more than one of the 2–3 suggested outfits in a single request.

### 3.3 Family Ecosystem & COPPA Compliance

- **Guardian account** is the root; can spawn up to N kid sub-profiles.
- Kid sub-profiles have:
  - No standalone login (PIN/biometric handoff from guardian device only).
  - No chat, no social, no third-party ads.
  - Affiliate shopping suggestions **disabled** by default and require explicit guardian opt-in.
- Kid UI mode:
  - Larger touch targets, rounded shapes, friendly mascot.
  - Outfits presented as "missions" ("Dress for the playground!") with stickers earned for completion.
  - Reading-light copy; pictograms for non-readers.
- **COPPA-required**: verifiable parental consent at sub-profile creation, data minimization (no precise location, no biometric storage), deletion-on-request workflow, and a clear privacy notice in onboarding.

### 3.4 Closet Gap Analysis & Affiliate Monetization

- Background job analyzes the user's wardrobe for missing staples by persona archetype (e.g., "capsule wardrobe" reference set).
- Surfaces 2–3 actionable gaps ("You're missing a versatile black belt," "No neutral blazer for office days").
- For each gap, fetch 2–3 shoppable matches via affiliate APIs (initially **Brands For Less**, **Ounass**, with **Amazon Associates** as a fallback).
- Disclosed as sponsored; affiliate click → tracked with a per-user signed token for attribution.

**Monetization additional layers** (post-MVP):
- Premium tier (unlimited outfits per day, advanced occasion templates, travel packing assistant).
- Brand-sponsored "looks of the week" — clearly labeled.

## 4. Non-Functional Requirements

| Area | Requirement |
|---|---|
| **Latency** | Item upload → tagged ≤5s p95. Outfit generation ≤4s p95. |
| **Availability** | 99.9% monthly for core read/write paths. |
| **Privacy** | All wardrobe images encrypted at rest; signed URLs only; kid data isolated under COPPA controls. |
| **Internationalization** | Multi-currency for affiliate; metric/imperial; RTL-ready (Arabic) given Brands For Less / Ounass markets. |
| **Accessibility** | WCAG 2.1 AA in the mobile UI; full VoiceOver / TalkBack coverage. |

## 5. Success Metrics (North Star + Guardrails)

- **North star**: Weekly Outfit Generations per Active User (WOG/AU).
- **Engagement**: D1 / D7 / D30 retention; items uploaded per new user in week 1.
- **Monetization**: Affiliate click-through rate from gap analysis; revenue per active user.
- **Quality**: % of generated outfits accepted (not regenerated within 60s); manual tag correction rate (lower is better).
- **Trust**: Guardian-reported issues per 10k kid sessions (lower is better).

## 6. Out of Scope for MVP

- Peer-to-peer outfit sharing / social feed.
- In-app resale or second-hand marketplace.
- AR try-on.
- Custom tailoring / made-to-measure integration.

These are tracked for v2 once the core wardrobe + stylist loop has product-market fit.
