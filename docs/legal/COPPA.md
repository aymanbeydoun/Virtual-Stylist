# COPPA Compliance — Consent Flow

**Status**: Draft. Requires sign-off by counsel (US: FTC COPPA Rule, 16 CFR Part
312) before any feature that processes a child's data ships to users under 13.

This document specifies the *operational* flow. It is not legal advice. The
final consent text, retention policy, and Verifiable Parental Consent (VPC)
method must be reviewed and signed off by your retained counsel.

---

## 1. Scope — who is a "child" for our purposes

| Region | Threshold | Reference |
|---|---|---|
| USA   | < 13 yrs | COPPA Rule, 16 CFR § 312.2 |
| UAE   | < 18 yrs (or "child" under PDPL) | UAE Federal Decree-Law 45 of 2021 (PDPL) |
| EU/UK | < 16 yrs (member-state floor 13) | GDPR Art. 8 |
| KSA   | < 18 yrs | KSA PDPL 2021 |

We use **the highest applicable threshold per the user's jurisdiction**, with a
fail-safe default of **< 18 yrs** when jurisdiction is unknown. Practically:
every family-member sub-profile under 18 enters the protected flow.

## 2. Data we collect about a child

Strictly limited to:

- **Photos of clothing items** the guardian uploads on the child's behalf.
- **A single base photo** of the child, used only for try-on rendering.
- **Display name + age range** (not exact DOB).
- **Generated outfits + worn/saved/skipped events**.

We do **not** collect:
- Email or contact info for the child.
- Geolocation precise to better than country.
- Behavioural ads identifiers (IDFA, etc.).
- Direct messaging or social features.

## 3. Verifiable Parental Consent (VPC)

The COPPA Rule offers several VPC methods. We use the **monetary-transaction
method (16 CFR § 312.5(b)(2)(iii))**:

1. Guardian taps "Add a child profile".
2. Modal:
   - Explains exactly what data is collected (§2 above).
   - Lists who has access (guardian only; no third-party advertising).
   - Explains the guardian's right to review, modify, or delete.
   - Provides the full text of the Privacy Notice (or a clear link).
3. Guardian taps **"I consent on behalf of my child"**.
4. App requires a **$0.50 payment authorisation** via Apple Pay / Google Pay
   (refunded automatically after 30 days — used purely to confirm adult
   identity via a payment-network-verified card).
5. We record:
   - `KidConsent.consent_method = 'card_check'`
   - `KidConsent.granted_at = now()`
   - `KidConsent.guardian_id = <guardian user id>`
   - Apple/Google transaction reference (in `kid_consents` extension column,
     **NOT** card number or PII).

Alternative method when in-app payment isn't available: **signed digital
consent form (§ 312.5(b)(2)(vi))** with parent ID upload.

## 4. The consent screen — required content

The screen MUST include, before the consent CTA:

> By tapping "I consent" you confirm that **[child's name]** is your child
> or you have legal authority to act on their behalf, and that you consent
> to Virtual Stylist collecting and processing:
>
> - Photos of clothing items you choose to upload on their behalf
> - One base photo used solely to generate try-on previews
> - Their display name and age range
> - Outfit selections and wear history
>
> This information is used **only** to provide the styling and try-on
> features inside Virtual Stylist. It is **never** shared with advertisers,
> never sold, and never combined with data from other apps. You can review,
> modify, or permanently delete your child's profile and all associated
> data at any time from **You → Family**.
>
> Photos are stored encrypted and processed by:
> - Anthropic (Claude API) — clothing tag inference
> - Replicate (Google nano-banana / SAM models) — background removal, try-on
> - Google Cloud Storage — encrypted storage
>
> No images leave the AI providers' systems for training. Read the full
> [Privacy Notice](./PRIVACY.md) (3-minute read).

## 5. Ongoing rights

The guardian can, from **You → Family → [child]**:

- **Review** — list every uploaded item + every generated outfit.
- **Modify** — change name, age range, kid-mode toggle.
- **Delete** — full account deletion. Triggers:
  - Hard delete of `wardrobe_items` rows with `coppa_protected=true`.
  - Hard delete of `family_members` row.
  - Audit-log entry that survives deletion (FTC-compliant).
  - Asynchronous purge of storage objects within 7 days.
  - Vendor data-purge requests to Anthropic + Replicate (their APIs do not
    retain inference inputs; we send the deletion request for compliance
    paper trail anyway).

## 6. Where this is implemented today

| Concern | File | Status |
|---|---|---|
| `kid_consents` audit table | `services/api/app/models/family.py` | ✅ schema |
| Sub-profile creation requires consent | `services/api/app/api/v1/family.py` | ⚠️ scaffold; payment-method check NOT wired |
| `coppa_protected=true` on kid items | `services/api/app/api/v1/wardrobe.py` | ✅ |
| Vendor-purge cron on deletion | not built | ❌ |
| Privacy Notice content | `docs/legal/PRIVACY.md` | ⚠️ draft |
| Consent screen UI | `apps/mobile/src/screens/Family/AddMemberScreen.tsx` | ⚠️ stub |

## 7. Open items before kid-mode ships

1. **Counsel review** of this doc, the consent screen text, and the Privacy
   Notice.
2. **VPC payment integration** — Apple Pay / Google Pay $0.50 hold flow.
3. **Vendor processing addenda** — get DPAs from Anthropic, Replicate, GCP
   on file (Anthropic publishes one; Replicate's terms need a custom DPA
   request for COPPA-covered data).
4. **App Store metadata** — declare data-collection categories truthfully
   in App Privacy.
5. **In-app right-to-review export** — JSON dump of all child data on
   guardian request, downloadable from the app.
6. **Data retention policy** — auto-delete kid profiles inactive for 24
   months (with email warning at 21).

## 8. Test scenarios to gate kid-mode launch

- [ ] Adult creates kid profile → consent screen shows → tap consent →
      payment auth succeeds → row created → `kid_consents` row recorded.
- [ ] Same flow with declined payment → no kid row created, no data stored.
- [ ] Guardian opens You → Family → kid → "Delete profile" → confirms →
      all wardrobe_items, outfits, base_photo deleted within 60 seconds;
      storage purged within 7 days; `kid_consents` audit row retained.
- [ ] Right-to-review JSON export contains every uploaded photo's storage
      key + every outfit ID + every event.
- [ ] No item under a kid profile is ever visible from another user's API
      query (RLS test).
