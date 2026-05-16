"""Single point of entry to all CV + LLM providers.

Two gateways:
  - StubGateway        : deterministic fake outputs, no network, no cost. Used in tests + when
                         MODEL_GATEWAY_BACKEND=stub.
  - ProductionGateway  : real CV + LLM.
      * background removal → Replicate (lucataco/remove-bg, ~$0.0023/run)
      * tagging            → Anthropic Claude Vision (returns structured JSON natively)
      * embeddings         → Replicate (krthr/clip-embeddings, 768-dim CLIP ViT-L/14)
      * stylist composition → Anthropic Claude (Sonnet for adults, Haiku for kid mode)

We split CV across two providers because:
  - Claude Vision is excellent at categorisation/colour/pattern reasoning but does not return
    embeddings, which we need for similarity / closet-gap analysis.
  - Replicate's CLIP endpoint is the cheapest path to a stable 768-dim embedding without
    standing up GPU infrastructure ourselves.
  - Replicate's bg-removal is faster + cleaner than asking Claude to mask.

Swap any leg without touching callers: every consumer depends on the ModelGateway Protocol.
"""
from __future__ import annotations

import asyncio
import base64
import json
import random
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import structlog

from app.config import get_settings
from app.schemas.common import ColorTag, ConfidenceScores, WeatherSnapshot

logger = structlog.get_logger()


@dataclass
class TagResult:
    category: str
    pattern: str
    colors: list[ColorTag]
    formality: int
    seasonality: list[str]
    embedding: list[float]
    confidence_scores: ConfidenceScores


@dataclass
class StylistResult:
    outfits: list[dict[str, Any]]
    model_id: str


@dataclass
class GapAnalysisResult:
    findings: list[dict[str, Any]]
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
        weather: WeatherSnapshot | None,
        notes: str | None,
        kid_mode: bool,
    ) -> StylistResult: ...
    async def analyze_gaps(
        self,
        *,
        items: list[dict[str, Any]],
        owner_label: str,
    ) -> GapAnalysisResult: ...


# ---------------------------------------------------------------------------
# Stub gateway — offline dev only
# ---------------------------------------------------------------------------

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
    async def tag_item(self, image_bytes: bytes) -> TagResult:
        seed = sum(image_bytes[:256]) if image_bytes else 0
        rng = random.Random(seed)
        return TagResult(
            category=rng.choice(_CATEGORIES),
            pattern=rng.choice(_PATTERNS),
            colors=[ColorTag(name="navy", hex="#1c2541", weight=0.7)],
            formality=rng.randint(2, 8),
            seasonality=rng.choice(_SEASONS),
            embedding=[rng.uniform(-1, 1) for _ in range(768)],
            confidence_scores=ConfidenceScores(
                root={"category": 0.92, "pattern": 0.81, "color": 0.95}
            ),
        )

    async def remove_background(self, image_bytes: bytes) -> bytes:
        return image_bytes

    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str,
        weather: WeatherSnapshot | None,
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
                            + (f" — packed for {weather.condition}." if weather else ".")
                        ),
                        "confidence": 0.78,
                    }
                )
        return StylistResult(outfits=outfits, model_id="stub-stylist-v0")

    async def analyze_gaps(
        self,
        *,
        items: list[dict[str, Any]],
        owner_label: str,
    ) -> GapAnalysisResult:
        slots_present = {it.get("slot") for it in items if it.get("slot")}
        findings: list[dict[str, Any]] = []
        if "top" in slots_present and "bottom" in slots_present and "shoes" not in slots_present:
            findings.append(
                {
                    "slot": "shoes",
                    "category_hint": "shoes.casual_sneaker",
                    "title": "A pair of versatile sneakers",
                    "rationale": "You have tops and bottoms but no shoes to anchor them.",
                    "severity": "high",
                    "search_query": "white leather sneakers women",
                }
            )
        if "shoes" in slots_present and not any(
            "belt" in str(it.get("category", "")).lower() for it in items
        ):
            findings.append(
                {
                    "slot": "accessory",
                    "category_hint": "accessories.belts.leather",
                    "title": "A black leather belt",
                    "rationale": "Pulls outfits together; missing from your closet today.",
                    "severity": "medium",
                    "search_query": "black leather belt",
                }
            )
        return GapAnalysisResult(findings=findings, model_id="stub-gaps-v0")


# ---------------------------------------------------------------------------
# Production gateway — Replicate + Anthropic
# ---------------------------------------------------------------------------

_TAGGING_SYSTEM = """\
You are a fashion catalogue tagger. Given a single clothing item photo, return ONLY a
JSON object with this exact shape — no markdown, no prose:

{
  "category": "<gender>.<group>.<subcategory>",
  "pattern": "solid|stripe|floral|graphic|plaid|other",
  "colors": [
    {"name": "<color name>", "hex": "#RRGGBB", "weight": 0.0-1.0}
  ],
  "formality": 1-10,
  "seasonality": ["spring"|"summer"|"fall"|"winter", ...],
  "confidence_scores": {"category": 0.0-1.0, "pattern": 0.0-1.0, "color": 0.0-1.0}
}

Category guide:
- <gender> is one of: womens, mens, kids, accessories.
- Use 'accessories' for jewelry, belts, hats, bags, scarves.
- Examples: 'womens.tops.blouse', 'mens.shoes.loafer', 'kids.bottoms.shorts',
  'accessories.jewelry.necklace'.

Formality scale: 1=loungewear, 5=smart-casual, 10=black-tie.

Rules:
- Return 1-3 dominant colors. Weights sum to ~1.0, sorted by weight descending.
- Hex must be a real 6-digit color present in the photo. No #000000 placeholders.
- If unsure on any field, lower its confidence score. Never invent.
- Output ONLY the JSON object. No code fences. No commentary.
"""


_STYLIST_SYSTEM = """\
You are a professional personal stylist working from the user's actual wardrobe.

You receive a JSON payload with: destination, mood, weather, notes, kid_mode, and a list \
of `candidates`. Each candidate has: id, slot (top|bottom|dress|shoes|outerwear|accessory), \
category, colors, pattern, formality, seasonality.

Compose 2-3 complete outfits. Hard rules:
- Each outfit MUST include shoes.
- Each outfit MUST include either (a) one top + one bottom, OR (b) one dress.
- Never repeat the same item across outfits.
- Respect the weather (temp_c, condition). Cold/rain → outerwear, never sandals.
- Match formality to destination (office=6-8, date=6-9, playground=2-4, gym=1-3).
- Include accessories (jewelry/belt/hat/bag) when they elevate the look.

Output ONLY this JSON, no markdown:
{
  "outfits": [
    {
      "items": [{"item_id": "<id>", "slot": "<slot>"}, ...],
      "rationale": "<one sentence, second person, why this works>",
      "confidence": 0.0-1.0
    }
  ]
}
"""

_STYLIST_KID_SUFFIX = (
    "\n\nThe wearer is a child. Keep rationales playful, encouraging, and under 15 words. "
    "Avoid any product/brand names."
)

_GAP_SYSTEM = """\
You analyse the user's wardrobe to identify the 3-5 most impactful missing items.

You receive a JSON list of `items` (each with slot, category, colors, pattern, formality,
seasonality) plus an owner_label like "You" or "Sara".

A 'gap' is a specific, actionable hole — not a category buzzword. Bad: 'add more variety'.
Good: 'a versatile black leather belt to anchor smart-casual looks'.

Rules:
- Identify gaps that materially expand the outfit space. Skip nice-to-haves until staples
  are filled.
- Prefer slots that unlock new outfits (shoes, outerwear, bottoms) over ones already covered.
- Each gap MUST be specific enough to shop for: include a color hint and a usage rationale.
- Tag severity:
    'high'   = wardrobe is dysfunctional without it (eg. no shoes at all).
    'medium' = limits outfit count significantly (eg. no black belt for smart casual).
    'low'    = nice upgrade but optional.

Output ONLY this JSON shape, no markdown:
{
  "findings": [
    {
      "slot": "shoes|top|bottom|outerwear|accessory|jewelry|dress",
      "category_hint": "<dotted category like 'mens.shoes.loafer'>",
      "title": "<5-10 word noun phrase the user could shop for>",
      "rationale": "<one sentence, second person, why this gap matters>",
      "severity": "high|medium|low",
      "search_query": "<2-6 word phrase for affiliate search>"
    }
  ]
}
"""


def _detect_image_media_type(image_bytes: bytes) -> str:
    """Sniff the actual media type from magic bytes.

    Replicate's bg-removal returns PNG (transparent background) even when fed a
    JPEG, so we can't assume the source format survives the pipeline. Claude
    Vision rejects requests where the declared media_type doesn't match the
    payload, so we detect from the first few bytes and pass through accurately.
    """
    if len(image_bytes) < 8:
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _color_from_payload(raw: dict[str, Any]) -> ColorTag:
    """Coerce an LLM-returned color dict into a strict ColorTag.

    Claude sometimes returns hex without the leading '#' (e.g. 'C8150A') even when
    the prompt asks for '#RRGGBB'. We normalise rather than re-prompt — cheaper
    and more reliable. Falls back to lowercasing for canonical form.
    """
    hex_value = str(raw.get("hex", "")).strip()
    if hex_value and not hex_value.startswith("#"):
        hex_value = "#" + hex_value
    hex_value = hex_value.lower()
    if not re.match(r"^#[0-9a-f]{6}$", hex_value):
        hex_value = "#888888"  # neutral grey if Claude returned something unparseable
    weight = float(raw.get("weight", 0.0))
    weight = max(0.0, min(1.0, weight))
    return ColorTag(name=str(raw.get("name", "unknown")), hex=hex_value, weight=weight)


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM response, tolerant of ```json fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        parsed: dict[str, Any] = json.loads(fenced.group(1))
        return parsed
    brace = text.find("{")
    if brace == -1:
        raise ValueError(f"no JSON object in response: {text[:200]}")
    parsed = json.loads(text[brace:])
    return parsed


class ProductionGateway:
    """Real AI: Replicate for CV bg-removal + embeddings, Anthropic for tagging + stylist."""

    def __init__(
        self,
        *,
        anthropic_api_key: str,
        replicate_api_token: str,
        anthropic_model: str,
        anthropic_vision_model: str,
        bg_removal_model: str,
        clip_model: str,
    ) -> None:
        from anthropic import AsyncAnthropic

        self._anthropic = AsyncAnthropic(api_key=anthropic_api_key)
        self._replicate_token = replicate_api_token
        self._anthropic_model = anthropic_model
        self._anthropic_vision_model = anthropic_vision_model
        self._bg_removal_model = bg_removal_model
        self._clip_model = clip_model
        self._http = httpx.AsyncClient(
            base_url="https://api.replicate.com/v1",
            headers={"Authorization": f"Token {replicate_api_token}"},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        # Replicate's free / low-credit tier throttles to ~6 req/min with 1 burst.
        # Even on paid plans, serialising avoids stampedes when the worker
        # processes a batch. The semaphore guarantees one in-flight prediction
        # at a time; combined with the 429 retry in _run_replicate, batches
        # process slowly but reliably without burning credits on retries.
        self._replicate_semaphore = asyncio.Semaphore(1)

    async def remove_background(self, image_bytes: bytes) -> bytes:
        """Replicate-based bg removal. Degrades to a pass-through on any failure
        so the rest of the pipeline (Claude Vision tagging) still runs.

        We intentionally swallow exceptions here because background removal is
        a quality upgrade, not a correctness requirement. The tagger only needs
        the photo; the user just loses the cutout look.
        """
        if not self._replicate_token:
            return image_bytes
        try:
            data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
            _, version = self._bg_removal_model.split(":", 1)
            result_url = await self._run_replicate(version, {"image": data_url})
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(result_url)
                r.raise_for_status()
                return r.content
        except Exception as exc:
            logger.warning(
                "replicate.bg_removal_failed",
                exc_info=False,
                error_type=type(exc).__name__,
                error_msg=str(exc)[:160],
            )
            return image_bytes

    async def tag_item(self, image_bytes: bytes) -> TagResult:
        category, pattern, colors, formality, seasonality, confidence = await self._tag_with_claude(
            image_bytes
        )
        embedding = await self._embed_clip(image_bytes)
        return TagResult(
            category=category,
            pattern=pattern,
            colors=colors,
            formality=formality,
            seasonality=seasonality,
            embedding=embedding,
            confidence_scores=ConfidenceScores(root=confidence),
        )

    async def _tag_with_claude(
        self, image_bytes: bytes
    ) -> tuple[str, str, list[ColorTag], int, list[str], dict[str, float]]:
        media_type = _detect_image_media_type(image_bytes)
        b64 = base64.b64encode(image_bytes).decode()
        # The Anthropic SDK's MessageParam type is a typed dict; declared inline
        # here as Any-typed so we can use the dynamic media_type. The runtime
        # API accepts any valid image/{jpeg,png,gif,webp}.
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            },
            {"type": "text", "text": "Tag this item."},
        ]
        msg = await self._anthropic.messages.create(
            model=self._anthropic_vision_model,
            max_tokens=600,
            system=_TAGGING_SYSTEM,
            messages=[{"role": "user", "content": content}],  # type: ignore[typeddict-item]
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        parsed = _extract_json(text)
        return (
            parsed["category"],
            parsed["pattern"],
            [_color_from_payload(c) for c in parsed["colors"]],
            int(parsed["formality"]),
            parsed["seasonality"],
            {k: float(v) for k, v in parsed["confidence_scores"].items()},
        )

    async def _embed_clip(self, image_bytes: bytes) -> list[float]:
        """Replicate CLIP embedding. Returns zeros on failure so similarity
        search degrades gracefully rather than crashing the ingest pipeline.
        """
        if not self._replicate_token:
            return [0.0] * 768
        try:
            data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
            _, version = self._clip_model.split(":", 1)
            result = await self._run_replicate(version, {"image": data_url}, expect="json")
            if isinstance(result, dict) and "embedding" in result:
                return [float(x) for x in result["embedding"]]
            if isinstance(result, list):
                return [float(x) for x in result]
            raise ValueError(f"unexpected clip output: {type(result).__name__}")
        except Exception as exc:
            logger.warning(
                "replicate.embedding_failed",
                error_type=type(exc).__name__,
                error_msg=str(exc)[:160],
            )
            return [0.0] * 768

    async def _run_replicate(
        self, version: str, input_payload: dict[str, Any], expect: str = "url"
    ) -> Any:
        """Create a prediction and poll until it succeeds.

        Replicate predictions are async — create returns immediately with status='starting',
        and we have to poll the get endpoint until status is succeeded/failed/canceled.

        Retries on 429 (rate limit) and 5xx (transient) with exponential backoff.
        402 (Payment Required) is a permanent config error — raises immediately.
        Serialised via a per-gateway semaphore so concurrent ingest jobs don't
        stampede the rate limiter.
        """
        async with self._replicate_semaphore:
            # Retry the create-call: this is where rate-limiting bites first.
            delay = 2.0
            for attempt in range(6):
                create = await self._http.post(
                    "/predictions",
                    json={"version": version, "input": input_payload},
                )
                if create.status_code == 402:
                    raise RuntimeError(
                        "Replicate returned 402 Payment Required — add billing at "
                        "https://replicate.com/account/billing"
                    )
                if create.status_code == 429 or create.status_code >= 500:
                    if attempt == 5:
                        create.raise_for_status()
                    # Replicate sets retry_after in the body for 429s; honour that
                    # if present, otherwise fall back to exponential backoff.
                    body = (
                        create.json() if "application/" in create.headers.get("content-type", "")
                        else {}
                    )
                    retry_after = float(
                        body.get("retry_after")
                        or create.headers.get("retry-after")
                        or delay
                    )
                    await asyncio.sleep(min(max(retry_after, 1.0) + 1.0, 30.0))
                    delay = min(delay * 2, 30.0)
                    continue
                create.raise_for_status()
                break

        pred = create.json()
        get_url = pred["urls"]["get"]

        for _ in range(120):  # ~2 min ceiling
            await asyncio.sleep(1.0)
            poll = await self._http.get(get_url)
            poll.raise_for_status()
            pred = poll.json()
            status = pred["status"]
            if status == "succeeded":
                out = pred["output"]
                if isinstance(out, list) and out and isinstance(out[0], str):
                    return out[0] if expect == "url" else out
                return out
            if status in ("failed", "canceled"):
                raise RuntimeError(f"replicate prediction {status}: {pred.get('error')}")
        raise TimeoutError(f"replicate prediction did not complete: {pred.get('id')}")

    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str,
        weather: WeatherSnapshot | None,
        notes: str | None,
        kid_mode: bool,
    ) -> StylistResult:
        model = "claude-haiku-4-5" if kid_mode else self._anthropic_model
        system = _STYLIST_SYSTEM + (_STYLIST_KID_SUFFIX if kid_mode else "")
        payload = {
            "destination": destination,
            "mood": mood,
            "weather": weather.model_dump(mode="json") if weather else None,
            "notes": notes,
            "kid_mode": kid_mode,
            "candidates": candidates,
        }
        msg = await self._anthropic.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        parsed = _extract_json(text)
        return StylistResult(outfits=parsed["outfits"], model_id=model)

    async def analyze_gaps(
        self,
        *,
        items: list[dict[str, Any]],
        owner_label: str,
    ) -> GapAnalysisResult:
        payload = {"owner_label": owner_label, "items": items}
        msg = await self._anthropic.messages.create(
            model=self._anthropic_model,
            max_tokens=1500,
            system=_GAP_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        parsed = _extract_json(text)
        return GapAnalysisResult(
            findings=parsed.get("findings", []),
            model_id=self._anthropic_model,
        )

    async def aclose(self) -> None:
        await self._http.aclose()


# Module-level singleton: lru_cache wouldn't work because httpx clients need an
# event-loop context, and the gateway is fetched per-request.
_gateway_instance: ModelGateway | None = None


def get_model_gateway() -> ModelGateway:
    """Return the configured gateway. Falls back to stub on missing keys."""
    global _gateway_instance
    if _gateway_instance is not None:
        return _gateway_instance

    s = get_settings()
    if s.model_gateway_backend == "anthropic" and s.anthropic_api_key:
        _gateway_instance = ProductionGateway(
            anthropic_api_key=s.anthropic_api_key,
            replicate_api_token=s.replicate_api_token,
            anthropic_model=s.anthropic_model,
            anthropic_vision_model=s.anthropic_vision_model,
            bg_removal_model=s.replicate_bg_removal_model,
            clip_model=s.replicate_clip_model,
        )
    else:
        _gateway_instance = StubGateway()
    return _gateway_instance


def _reset_gateway_for_tests() -> None:
    """Test helper — drop the singleton so a new gateway is built on next call."""
    global _gateway_instance
    _gateway_instance = None


# Re-export for any callers that still import these names.
class AnthropicGateway(ProductionGateway):
    """Back-compat alias: previous module exposed AnthropicGateway."""

    def __init__(self, api_key: str) -> None:
        s = get_settings()
        super().__init__(
            anthropic_api_key=api_key,
            replicate_api_token=s.replicate_api_token,
            anthropic_model=s.anthropic_model,
            anthropic_vision_model=s.anthropic_vision_model,
            bg_removal_model=s.replicate_bg_removal_model,
            clip_model=s.replicate_clip_model,
        )


