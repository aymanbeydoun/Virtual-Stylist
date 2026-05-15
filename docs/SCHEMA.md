# Database Schema (High-Level)

PostgreSQL 16, with `pgvector` and `pgcrypto`. UUIDv7 primary keys for time-sortable
identifiers and clean sharding later. Soft-delete via `deleted_at` everywhere
that holds user-generated content.

## 1. Identity & Family

### `users`
Primary account holder. Guardians and standalone adults live in the same table;
the `role` column distinguishes them.

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | UUIDv7 |
| `email` | citext unique | from auth provider |
| `auth_provider_id` | text unique | Auth0 / Clerk subject |
| `role` | enum(`adult`, `guardian`) | `guardian` can own sub-profiles |
| `display_name` | text | |
| `locale` | text | e.g. `en-AE`, drives currency + RTL |
| `birth_year` | smallint | for sizing heuristics, not exact DOB |
| `created_at` / `updated_at` / `deleted_at` | timestamptz | |

### `family_members`
Sub-profiles owned by a guardian. Kids live here, never in `users`.

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `guardian_id` | uuid → `users.id` | indexed |
| `display_name` | text | kid's first name only |
| `kind` | enum(`adult`, `teen`, `kid`) | drives UI mode + monetization gates |
| `birth_year` | smallint | for sizing only |
| `kid_mode` | bool | enables gamified UI |
| `created_at` / `deleted_at` | timestamptz | |

### `kid_consents` (COPPA)
Append-only.

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `family_member_id` | uuid → `family_members.id` | |
| `guardian_id` | uuid → `users.id` | |
| `consent_method` | enum(`card_check`, `signed_id`, `kba`) | |
| `granted_at` | timestamptz | |
| `revoked_at` | timestamptz null | |

### `style_profiles`
One per `users` or `family_members` (polymorphic owner).

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `owner_kind` | enum(`user`, `family_member`) | |
| `owner_id` | uuid | composite index with `owner_kind` |
| `sizes` | jsonb | `{top: "M", bottom: "32", shoe_eu: 42}` |
| `style_vector` | vector(768) | running average of accepted outfit embeddings |
| `preferred_colors` | text[] | |
| `disliked_categories` | text[] | |
| `updated_at` | timestamptz | |

---

## 2. Wardrobe

### `wardrobe_items`

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `owner_kind` | enum(`user`, `family_member`) | |
| `owner_id` | uuid | composite index |
| `raw_image_key` | text | GCS path |
| `cutout_image_key` | text | background-removed |
| `thumbnail_key` | text | 256px |
| `category` | text | e.g. `womens.shoes.stiletto`, `kids.tops.graphic_tee` |
| `subcategory_path` | ltree | hierarchical for fast prefix queries |
| `colors` | jsonb | `[{name: "navy", hex: "#1c2541", weight: 0.62}, …]` |
| `pattern` | enum(`solid`,`stripe`,`floral`,`graphic`,`plaid`,`other`) | |
| `formality` | smallint (0–10) | 0 = athleisure, 10 = black tie |
| `seasonality` | text[] | subset of `{spring,summer,fall,winter}` |
| `material_guess` | text null | |
| `embedding` | vector(768) | CLIP, ivfflat index |
| `confidence_scores` | jsonb | per-attribute, for "needs review" UI |
| `needs_review` | bool | computed from confidence |
| `coppa_protected` | bool | true when owner is a kid family_member |
| `created_at` / `deleted_at` | timestamptz | |

Indexes:
- `(owner_kind, owner_id, category)` for closet browsing.
- `ivfflat (embedding vector_cosine_ops)` for similarity search.
- `gist (subcategory_path)` for hierarchical filters.

### `item_corrections`
User-driven edits, feeds retraining queue.

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `item_id` | uuid → `wardrobe_items.id` | |
| `field` | text | e.g. `category`, `pattern` |
| `old_value` / `new_value` | text | |
| `corrected_at` | timestamptz | |

---

## 3. Outfits

### `outfits`

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `owner_kind` / `owner_id` | enum / uuid | |
| `source` | enum(`ai_generated`, `user_saved`, `manual`) | |
| `destination` | text null | `office`, `date`, … |
| `mood` | text null | `confident`, `cozy`, … |
| `weather_snapshot` | jsonb | `{temp_c, condition, wind_kph}` at generation |
| `rationale` | text null | LLM-authored "why this works" |
| `model_id` | text null | which LLM produced it (audit) |
| `accepted` | bool null | did the user save / wear it? |
| `composite_image_key` | text | flat-lay render |
| `created_at` | timestamptz | |

### `outfit_items` (join)

| column | type | notes |
|---|---|---|
| `outfit_id` | uuid → `outfits.id` | pk part |
| `item_id` | uuid → `wardrobe_items.id` | pk part |
| `slot` | enum(`top`,`bottom`,`dress`,`outerwear`,`shoes`,`accessory`,`jewelry`) | |

### `outfit_events`
Records of "I wore this today" — drives the no-repeat heuristic and retention loops.

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `outfit_id` | uuid → `outfits.id` | |
| `event_kind` | enum(`worn`,`skipped`,`regenerated`) | |
| `occurred_at` | timestamptz | |

---

## 4. Commerce

### `gap_findings`
One row per detected closet gap, refreshed daily.

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `owner_kind` / `owner_id` | enum / uuid | |
| `gap_label` | text | e.g. `versatile_black_belt` |
| `priority_score` | float | |
| `discovered_at` / `dismissed_at` | timestamptz | |

### `affiliate_suggestions`

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `gap_id` | uuid → `gap_findings.id` | |
| `network` | enum(`brands_for_less`,`ounass`,`amazon`) | |
| `external_product_id` | text | |
| `title` | text | |
| `image_url` | text | CDN-cached |
| `price` | numeric | |
| `currency` | text | |
| `deeplink` | text | with our affiliate token |
| `fetched_at` | timestamptz | TTL 24h |

### `affiliate_clicks`

| column | type | notes |
|---|---|---|
| `id` | uuid (pk) | |
| `user_id` | uuid → `users.id` | |
| `suggestion_id` | uuid → `affiliate_suggestions.id` | |
| `clicked_at` | timestamptz | |
| `attribution_token` | text | signed, included in deeplink |

---

## 5. Cross-cutting Conventions

- All mutating endpoints stamp `updated_by` with the acting principal (guardian id if acting on a kid's row).
- Row-level security policies: any row tagged with `coppa_protected=true` is readable only by the owning guardian.
- Soft delete via `deleted_at`; a nightly job hard-deletes rows 30 days past their deletion timestamp.
- Migrations: Alembic, one file per change, never edited after merge.
