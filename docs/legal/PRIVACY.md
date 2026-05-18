# Virtual Stylist — Privacy Notice (DRAFT)

**Status**: Draft. Replace placeholder operator details and have counsel
review before publishing.

**Last updated**: 17 May 2026

**Operator**: [REGISTERED ENTITY NAME], [REGISTERED ADDRESS], UAE
**Contact**: privacy@virtualstylist.app
**Data Protection Officer**: [DPO NAME], [DPO EMAIL]

---

## 1. What we are

Virtual Stylist is a mobile app that helps you and your family decide what
to wear, using AI to tag the clothes you already own and propose outfits.

## 2. What we collect — and why

| Data | Why | Stored where | How long |
|---|---|---|---|
| Email / Auth0 ID | Sign you in | Auth0 (EU) + our DB | Until you delete your account |
| Display name | Greet you in the app | Our DB | Until you delete |
| Country (not precise location) | Localise destinations (Mall, etc.) | Our DB | Until you delete |
| Photos of your clothes | Tag them so the AI knows your wardrobe | GCS bucket (CMEK-encrypted) | Until you delete the item |
| Optional: base photo of you | Render try-on previews | GCS bucket (CMEK-encrypted) | Until you delete or replace it |
| Outfit history (worn / saved / skipped) | Avoid repeating outfits, learn your preferences | Our DB | Rolling 24 months |
| AI chat messages about outfits | Show the refinement thread | Our DB | Until you delete the outfit |

We do **not** collect:
- Precise geolocation.
- Behavioural advertising identifiers (IDFA, AAID).
- Health / financial / biometric data beyond your face image in the
  optional base photo, which is **never** used for identification.
- Voice or microphone data.

## 3. Children's data (COPPA / GDPR-K / UAE PDPL)

Children's profiles are created and managed by a guardian under a
Verifiable Parental Consent flow. Full details in [COPPA.md](./COPPA.md).
Short version:

- We require monetary-card-check or signed-ID consent before any data
  about a child is processed.
- We collect strictly less data for children (no email, no chat).
- A guardian can review, modify, or permanently delete a child's data at
  any time from **You → Family**.

## 4. Who sees your data

| Recipient | What | Why | Where |
|---|---|---|---|
| Anthropic (Claude API) | Photo of one clothing item at a time + an outfit composition prompt | AI tagging + outfit + chat refinement | US, by Anthropic's commercial agreement |
| Replicate | Photo of one item at a time | Background removal + CLIP embedding + try-on rendering | US, by Replicate's commercial agreement |
| Google Cloud Platform | Encrypted blobs + Postgres rows | Hosting | EU-region (Frankfurt) |
| Auth0 | Email + Auth0-issued ID | Sign-in | EU-region |
| OpenWeatherMap | Approximate location (city-level) when you generate an outfit | Weather-aware styling | US |

No data is sold. No data is used for advertising. No data is shared with
fashion retailers or affiliates **except**: when you tap a "Shop the look"
product card under Closet Gaps, the linked retailer receives a referral
parameter so we can be credited the commission if you buy. The retailer
does not receive your name, email, or any other personal data from us.

## 5. AI training

We do not use your data to train AI models. Anthropic and Replicate also
do not use our API requests to train their models — this is covered by
their commercial terms which we've reviewed and accepted on your behalf.

## 6. Security

- All photos are encrypted at rest (AES-256, customer-managed keys via
  Google KMS).
- All in-flight traffic is TLS 1.3.
- Database access is restricted to the API service account; no direct
  console access in production.
- Auth0 enforces MFA-by-default for adult sign-ins via passkeys.

## 7. Your rights

You have the right to:

1. **Access** — download a complete JSON export of your data and every
   item / outfit photo. Go to **You → Privacy → Export my data**.
2. **Correct** — fix any wrong tag on a wardrobe item (tap an item →
   Correct).
3. **Delete** — permanently delete your account, your family members'
   accounts, or any individual item. Deletion is final and complete
   within 30 days (audit log entry retained 12 months for COPPA / fraud).
4. **Object / restrict** — tell us not to use specific photos for try-on
   rendering, while keeping them for closet management.
5. **Portability** — export is JSON + the original photo files. Same as
   Access.
6. **Complain** — to your local DPA (UAE: TDRA Data Office; EU: your
   member-state DPA; US: FTC).

To exercise any right, email **privacy@virtualstylist.app**. We respond
within **30 days** (15 for UAE residents per PDPL).

## 8. Cookies / tracking

The app does not use cookies. We use no third-party analytics SDKs (no
Firebase Analytics, no Mixpanel, no Branch, no AppsFlyer). We use only
crash reports via [Sentry / native crash reporter] which collects:
device model, OS version, app version, stack trace — no PII.

## 9. International transfers

Data may be transferred between the EU (Auth0, GCP) and US (Anthropic,
Replicate) under Standard Contractual Clauses (SCCs) per GDPR Art. 46 and
Data Privacy Framework where the recipient is enrolled.

## 10. Changes

We'll notify you in the app at least 30 days before any change that
expands what we collect or who sees it. Minor wording updates are listed
at the bottom of this page.

## 11. Contact

- **General**: privacy@virtualstylist.app
- **Data Protection Officer**: [DPO NAME] <[DPO EMAIL]>
- **Security incidents**: security@virtualstylist.app

---

*This Privacy Notice is a working draft and requires legal review before
publication. Specific factual claims (model providers' training-data
policies, retention windows, encryption at-rest configuration) must be
verified against the actual production deployment before going live.*
