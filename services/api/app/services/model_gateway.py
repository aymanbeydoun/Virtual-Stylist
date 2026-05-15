"""Single point of entry to all CV + LLM providers."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import get_settings


@dataclass
class TagResult:
    category: str
    pattern: str
    colors: list[dict[str, Any]]
    formality: int
    seasonality: list[str]
    embedding: list[float]
    confidence_scores: dict[str, float]


@dataclass
class StylistResult:
    outfits: list[dict[str, Any]]
    model_id: str


class ModelGateway(Protocol):
    async def tag_item(self, image_bytes: bytes) -> TagResult: ...
    async def remove_background(self, image_bytes: bytes) -> bytes: ...
    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str,
        weather: dict[str, Any] | None,
        notes: str | None,
        kid_mode: bool,
    ) -> StylistResult: ...


_CATEGORIES = [
    "womens.tops.blouse",
    "womens.bottoms.jeans",
    "womens.dresses.midi",
    "womens.shoes.sneaker",
    "womens.shoes.stiletto",
    "mens.tops.tshirt",
    "mens.bottoms.chinos",
    "mens.shoes.loafer",
    "mens.accessories.fedora",
    "kids.tops.graphic_tee",
    "kids.bottoms.shorts",
    "accessories.jewelry.necklace",
    "accessories.belts.leather",
]
_PATTERNS = ["solid", "stripe", "floral", "graphic", "plaid", "other"]
_SEASONS = [["spring", "summer"], ["fall", "winter"], ["spring", "fall"], ["summer"]]


class StubGateway:
    """Deterministic-ish gateway for development. Replace with real providers."""

    async def tag_item(self, image_bytes: bytes) -> TagResult:
        seed = sum(image_bytes[:256]) if image_bytes else 0
        rng = random.Random(seed)
        return TagResult(
            category=rng.choice(_CATEGORIES),
            pattern=rng.choice(_PATTERNS),
            colors=[{"name": "navy", "hex": "#1c2541", "weight": 0.7}],
            formality=rng.randint(2, 8),
            seasonality=rng.choice(_SEASONS),
            embedding=[rng.uniform(-1, 1) for _ in range(768)],
            confidence_scores={"category": 0.92, "pattern": 0.81, "color": 0.95},
        )

    async def remove_background(self, image_bytes: bytes) -> bytes:
        return image_bytes

    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str,
        weather: dict[str, Any] | None,
        notes: str | None,
        kid_mode: bool,
    ) -> StylistResult:
        by_slot: dict[str, list[dict[str, Any]]] = {}
        for c in candidates:
            by_slot.setdefault(c["slot"], []).append(c)

        outfits: list[dict[str, Any]] = []
        n_outfits = 2 if kid_mode else 3
        max_per_slot = min(len(v) for v in by_slot.values()) if by_slot else 0
        for i in range(min(n_outfits, max(1, max_per_slot))):
            picked = []
            for slot, items in by_slot.items():
                if i < len(items):
                    picked.append({"item_id": items[i]["id"], "slot": slot})
            if picked:
                outfits.append(
                    {
                        "items": picked,
                        "rationale": (
                            f"A {mood} look for {destination.replace('_', ' ')}"
                            + (f" — packed for {weather.get('condition')}." if weather else ".")
                        ),
                        "confidence": 0.78,
                    }
                )
        return StylistResult(outfits=outfits, model_id="stub-stylist-v0")


class AnthropicGateway:
    def __init__(self, api_key: str) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)

    async def tag_item(self, image_bytes: bytes) -> TagResult:
        raise NotImplementedError("CV tagging routes to Vertex; configure separately")

    async def remove_background(self, image_bytes: bytes) -> bytes:
        raise NotImplementedError("Background removal routes to Vertex; configure separately")

    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str,
        weather: dict[str, Any] | None,
        notes: str | None,
        kid_mode: bool,
    ) -> StylistResult:
        model = "claude-haiku-4-5" if kid_mode else "claude-sonnet-4-6"
        system = (
            "You are a professional stylist. Given a JSON list of wardrobe items "
            "(each with id, slot, category, color, pattern, formality, seasonality), "
            "compose 2 or 3 complete outfits for the given destination and mood. "
            "Respect weather. Never repeat an item across outfits. "
            "Each outfit must include one top + one bottom (or one dress), shoes, "
            "and at least one accessory when available. "
            'Respond with ONLY JSON: {"outfits":[{"items":[{"item_id":"...","slot":"..."}],'
            '"rationale":"...","confidence":0.0}]}'
        )
        if kid_mode:
            system += " The user is a child — keep rationales playful, short, and age-appropriate."

        payload = {
            "destination": destination,
            "mood": mood,
            "weather": weather,
            "notes": notes,
            "candidates": candidates,
        }
        msg = await self._client.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text")
        parsed = json.loads(text)
        return StylistResult(outfits=parsed["outfits"], model_id=model)


def get_model_gateway() -> ModelGateway:
    settings = get_settings()
    if settings.model_gateway_backend == "anthropic" and settings.anthropic_api_key:
        return AnthropicGateway(settings.anthropic_api_key)
    return StubGateway()
