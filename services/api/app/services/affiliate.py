"""Affiliate provider protocol + a stub implementation for dev.

Real provider integrations (Brands For Less, Ounass, Amazon Product
Advertising) are deferred until you have credentials. The Protocol below is
the contract every provider must satisfy; mockable, swappable, no callers
need to know which network is on the other end.

To wire a real provider:
1. Implement AffiliateProvider for the SDK (e.g. ImpactAffiliateProvider).
2. Register it in `get_affiliate_provider()` keyed by env var.
3. Add credentials to .env (e.g. BFL_AFFILIATE_TOKEN).
4. Update the AffiliateProviderKind enum value to point at the new provider.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from typing import Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.affiliate import AffiliateProviderKind, AffiliateSuggestion
from app.models.gaps import GapFinding

logger = structlog.get_logger()


@dataclass
class ProductCandidate:
    """A product the provider believes matches the search query."""

    external_id: str
    title: str
    brand: str | None
    image_url: str | None
    price_minor: int | None  # smallest currency unit (AED fils, USD cents)
    price_currency: str | None  # ISO 4217
    affiliate_url: str
    provider: AffiliateProviderKind


class AffiliateProvider(Protocol):
    """Implement this for each affiliate network you wire."""

    name: AffiliateProviderKind

    async def search(self, query: str, max_results: int = 3) -> list[ProductCandidate]:
        """Search the provider's catalogue for the query. Sponsored placement
        rules are entirely the provider's responsibility — we just take what
        they return and surface it to the user.
        """
        ...


# ---------------------------------------------------------------------------
# Stub provider — visible product cards in dev, no real revenue.
# ---------------------------------------------------------------------------

# Hand-curated demo cards keyed by the slot/category-ish query stem. Lets the
# user see the affiliate UI before BFL/Ounass APIs are wired.
_STUB_CATALOGUE: dict[str, list[ProductCandidate]] = {
    "belt": [
        ProductCandidate(
            external_id="stub-belt-1",
            title="Reversible leather dress belt",
            brand="Tommy Hilfiger",
            image_url="https://images.unsplash.com/photo-1624222247344-550fb60583dc?w=600",
            price_minor=29900,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-belt-1",
            provider=AffiliateProviderKind.stub,
        ),
        ProductCandidate(
            external_id="stub-belt-2",
            title="Italian leather belt — black/tan reversible",
            brand="Massimo Dutti",
            image_url="https://images.unsplash.com/photo-1624222247344-550fb60583dc?w=600&sat=-20",
            price_minor=49500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-belt-2",
            provider=AffiliateProviderKind.stub,
        ),
    ],
    "shoe": [
        ProductCandidate(
            external_id="stub-shoe-1",
            title="Chelsea boot — black leather",
            brand="Common Projects",
            image_url="https://images.unsplash.com/photo-1614252369475-531eba835eb1?w=600",
            price_minor=149500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-shoe-1",
            provider=AffiliateProviderKind.stub,
        ),
        ProductCandidate(
            external_id="stub-shoe-2",
            title="Penny loafer — cognac suede",
            brand="Bass Weejuns",
            image_url="https://images.unsplash.com/photo-1605812860427-4024433a70fd?w=600",
            price_minor=89500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-shoe-2",
            provider=AffiliateProviderKind.stub,
        ),
    ],
    "shirt": [
        ProductCandidate(
            external_id="stub-shirt-1",
            title="Oxford button-down — white",
            brand="Brooks Brothers",
            image_url="https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=600",
            price_minor=39500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-shirt-1",
            provider=AffiliateProviderKind.stub,
        ),
        ProductCandidate(
            external_id="stub-shirt-2",
            title="Slim oxford shirt — light blue",
            brand="Charles Tyrwhitt",
            image_url="https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=600",
            price_minor=32500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-shirt-2",
            provider=AffiliateProviderKind.stub,
        ),
    ],
    "jacket": [
        ProductCandidate(
            external_id="stub-jacket-1",
            title="Navy medium-weight bomber",
            brand="Alpha Industries",
            image_url="https://images.unsplash.com/photo-1551803091-e20673f15770?w=600",
            price_minor=89500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-jacket-1",
            provider=AffiliateProviderKind.stub,
        ),
    ],
    "trouser": [
        ProductCandidate(
            external_id="stub-trouser-1",
            title="Slim charcoal wool trousers",
            brand="Reiss",
            image_url="https://images.unsplash.com/photo-1593030761757-71fae45fa0e7?w=600",
            price_minor=72500,
            price_currency="AED",
            affiliate_url="https://example.com/buy/stub-trouser-1",
            provider=AffiliateProviderKind.stub,
        ),
    ],
}


class StubAffiliateProvider:
    """Returns curated demo cards keyed by query keywords. No network calls."""

    name = AffiliateProviderKind.stub

    async def search(self, query: str, max_results: int = 3) -> list[ProductCandidate]:
        q = query.lower()
        for key, cards in _STUB_CATALOGUE.items():
            if key in q:
                return cards[:max_results]
        return []


# ---------------------------------------------------------------------------
# Service helpers
# ---------------------------------------------------------------------------


def get_affiliate_provider() -> AffiliateProvider:
    """Pick the provider based on env. Today we only have the stub —
    real providers register here as they come online.
    """
    settings = get_settings()
    # Future:
    #   if settings.bfl_affiliate_token: return BrandsForLessProvider(...)
    #   if settings.ounass_api_key: return OunassProvider(...)
    del settings
    return StubAffiliateProvider()


def _sign_attribution(suggestion_id: uuid.UUID) -> str:
    """Cheap signed token — ties the click back to a specific suggestion.

    Replace with HMAC-SHA256 over (suggestion_id, user_id, timestamp) keyed
    on a server secret once we have a real settlement flow. For now: a random
    nonce per suggestion is enough to make CSRF + spoofing harder.
    """
    return f"vs-{suggestion_id.hex[:12]}-{secrets.token_urlsafe(12)}"


async def suggestions_for_gap(
    db: AsyncSession,
    *,
    gap: GapFinding,
    max_results: int = 3,
) -> list[AffiliateSuggestion]:
    """Look up cached suggestions for this gap; lazy-fetch from the provider
    on first request. Idempotent — re-running won't duplicate.
    """
    existing = (
        await db.execute(
            select(AffiliateSuggestion).where(AffiliateSuggestion.gap_finding_id == gap.id)
        )
    ).scalars().all()
    if existing:
        return list(existing)

    provider = get_affiliate_provider()
    query = gap.search_query or gap.title
    candidates = await provider.search(query, max_results=max_results)
    inserted: list[AffiliateSuggestion] = []
    for c in candidates:
        s = AffiliateSuggestion(
            gap_finding_id=gap.id,
            provider=c.provider,
            external_id=c.external_id,
            title=c.title,
            brand=c.brand,
            image_url=c.image_url,
            price_minor=c.price_minor,
            price_currency=c.price_currency,
            affiliate_url=c.affiliate_url,
        )
        s.attribution_token = _sign_attribution(s.id)
        db.add(s)
        inserted.append(s)
    if inserted:
        await db.commit()
        for s in inserted:
            await db.refresh(s)
    return inserted
