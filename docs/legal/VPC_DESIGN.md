# Verifiable Parental Consent — Implementation Design

**Status:** Design ready. Implementation blocked on:
- Apple Developer Program enrollment ($99/yr)
- Apple Merchant ID
- Stripe (or Adyen) account with COPPA-compliant terms
- Counsel sign-off on `docs/legal/COPPA.md` + `docs/legal/PRIVACY.md`

Estimated implementation effort once unblocked: **2 working days** (1 mobile,
1 backend, parallelisable).

---

## Why we need this

COPPA Rule (16 CFR § 312.5) requires Verifiable Parental Consent (VPC) before
collecting personal information from a child under 13. The kid sub-profile
feature collects:
- Photos of the child's clothing
- A base photo of the child for try-on
- Display name + age range
- Outfit selections + wear history

Without VPC, every kid sub-profile is a regulatory liability. Today the
backend enforces `feature_kid_signup_enabled=false` (`services/api/app/config.py`)
— the endpoint returns 412 Precondition Failed. The mobile must surface this
as "Kid profiles coming soon."

---

## VPC method we'll use

**Monetary-transaction verification** (16 CFR § 312.5(b)(2)(iii)) — the
guardian authorises a small payment via a payment network that already
verified their identity (the issuing bank, via Apple Pay / Google Pay).

Why this method:
- Auth0 doesn't natively offer VPC. Some platforms use SMS + government ID
  (heavy friction). Our user base skews iPhone, where Apple Pay is 1-tap.
- Single charge of $0.50, immediately refunded after 30 days. Net cost to the
  guardian: zero. Net signal to us: an adult with a verified card said yes.
- Industry-standard — Yoti, KidGuard, and most YouTube Kids competitors use
  this method.

---

## Flow

```
[Mobile: Add Family Member]
        │  user picks kind="kid"
        ▼
[Mobile: Show consent screen — full copy from COPPA.md §4]
        │  user taps "I consent on behalf of my child"
        ▼
[Mobile: Apple Pay sheet, $0.50 hold]
        │  PaymentAuthorization completes (token signed by Apple)
        ▼
[Backend: POST /family/members]
        │  body includes:
        │    kind: "kid"
        │    apple_pay_token: <PKPaymentToken>  (or play_billing_token)
        │    consent_method: "card_check"
        ▼
[Backend: verify Apple Pay token with Stripe/Adyen]
        │  if valid → row created + KidConsent row recorded
        │  if invalid → 403, no row created
        ▼
[Backend: schedule $0.50 refund 30 days out]
```

---

## Schema additions needed

Already in `kid_consents` table:
- `id`, `family_member_id`, `guardian_id`, `consent_method`,
  `granted_at`, `revoked_at`

Add via follow-up migration:
- `payment_provider` text — "apple_pay" / "google_pay" / "stripe"
- `payment_provider_charge_id` text — reference for the refund
- `payment_refunded_at` timestamp — set when the refund clears

---

## Mobile changes

1. New screen `AddFamilyKidScreen` (parallel to existing `AddMemberScreen`)
   that shows the full COPPA.md §4 consent text + Apple Pay button.
2. iOS: `@stripe/stripe-react-native` (or `expo-apple-pay`) for the payment
   sheet. Native module — requires EAS Dev Build.
3. Android: `expo-payments-stripe` or Google Pay equivalent.

The mobile only sees the payment token; it never sees a card number or PAN.

---

## Backend changes

1. New `PaymentVerifier` Protocol with `StripePaymentVerifier` /
   `AdyenPaymentVerifier` implementations. Verifies the Apple Pay /
   Google Pay token against the provider and confirms a $0.50 charge
   succeeded.
2. Wire into the existing `create_member` endpoint behind the
   `kid` branch.
3. Daily cron that calls the payment provider's refund API for any
   `KidConsent` row older than 30 days without `payment_refunded_at`.
4. Audit-log all VPC verifications to a separate
   `compliance_audit_events` table (separate from normal app
   logging — retained 7 years per FTC).

---

## Right-to-review export

Required by COPPA + GDPR. Build:

```
POST /family/members/{id}/export
  → enqueues an export job
  → returns a signed S3/GCS URL valid for 24 hours
  → guardian downloads a zip containing:
      manifest.json       (all rows belonging to the kid)
      photos/             (every uploaded image)
      outfits/            (every generated outfit + composite)
```

---

## Deletion fan-out

Required by COPPA + GDPR. When a guardian deletes a kid sub-profile:

1. Mark `family_member.deleted_at` immediately.
2. Cascade hard-delete: `wardrobe_items`, `outfits`, `outfit_messages`,
   `outfit_tryons`, `gap_findings` where owner_id = kid.id.
3. Schedule background job:
   - Delete storage objects for all the kid's `raw_image_key` /
     `cutout_image_key` / `composite_image_key` / `rendered_image_key`.
   - Send vendor-purge requests to:
     - Anthropic (`POST /v1/data-deletion`)
     - Replicate (per their docs — currently file-a-ticket)
     - GCS (CMEK rotation per quarter for double protection).
4. Retain `kid_consents` audit row for 12 months (FTC requirement).

---

## Test cases for gating launch

- [ ] Adult flow: consent screen → declined Apple Pay → no row created.
- [ ] Adult flow: consent screen → approved Apple Pay → kid row + consent
      row + audit log entry, all linked.
- [ ] Refund cron runs 30 days later → consent.payment_refunded_at set.
- [ ] Guardian opens kid → Privacy → Export → JSON dump arrives via
      email link within 24h.
- [ ] Guardian deletes kid → all rows gone in 60s; storage purged in 7d.
- [ ] RLS test: another guardian can never read this kid's rows even
      with direct UUID guesses.

---

## Counsel sign-off checklist

Before flipping `feature_kid_signup_enabled=true`:

- [ ] COPPA.md reviewed + redlined by counsel.
- [ ] PRIVACY.md reviewed + redlined by counsel.
- [ ] Mobile consent screen copy reviewed.
- [ ] Apple Pay merchant agreement signed.
- [ ] Stripe COPPA addendum signed.
- [ ] Anthropic + Replicate DPAs on file.
- [ ] App Store "Data Used to Track You" / "Data Linked to You" /
      "Data Not Linked to You" categories filled accurately.
- [ ] Apple App Privacy questionnaire pre-filled and reviewed.
- [ ] Google Play Data Safety form filled and reviewed.
