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
from dataclasses import dataclass, field
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
    # Deep attributes — neckline, sleeve_length, fabric, fit, pattern_subtype,
    # embellishments, weight_class, waist_rise, hem_length, etc. Free-form so
    # we can evolve the taxonomy without re-deploying the schema.
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class StylistResult:
    outfits: list[dict[str, Any]]
    model_id: str


@dataclass
class GapAnalysisResult:
    findings: list[dict[str, Any]]
    model_id: str


@dataclass
class RefineResult:
    """Output of a one-turn refinement: the revised outfit + a chat reply."""

    items: list[dict[str, Any]]  # [{"item_id": "...", "slot": "..."}]
    rationale: str | None
    style: str | None
    message: str  # natural-language reply shown in the chat thread
    model_id: str


@dataclass
class TryonInput:
    """One garment image + its slot label, so the prompt can name what it is."""

    image_bytes: bytes
    slot: str  # 'top' | 'bottom' | 'outerwear' | 'shoes' | 'dress' | 'accessory'
    description: str | None = None  # eg. 'red leather sneaker'


@dataclass
class TryonResult:
    image_bytes: bytes
    model_id: str


@dataclass
class SegmentationMask:
    """One detected garment region with its alpha mask."""

    mask_bytes: bytes  # PNG with alpha channel
    bounding_box: tuple[int, int, int, int]  # (x, y, w, h)
    label: str | None = None  # what the segmenter thinks this is


@dataclass
class ClothingClassification:
    """Result of the zero-shot 'is this a clothing item?' gate.

    Runs BEFORE the bg-removal + tag calls so a photo of a cat or a landscape
    doesn't burn Replicate + Claude credits and end up cluttering the closet.
    """

    is_clothing: bool
    confidence: float  # 0.0-1.0, how sure we are about `is_clothing`
    detected_label: str  # eg "shirt", "cat", "food", "screenshot"
    reason: str | None = None  # human-friendly message for the mobile UI


class ModelGateway(Protocol):
    async def tag_item(self, image_bytes: bytes) -> TagResult: ...
    async def remove_background(
        self, image_bytes: bytes, quality_tier: str = "standard"
    ) -> bytes: ...
    async def classify_clothing(self, image_bytes: bytes) -> ClothingClassification:
        """Zero-shot 'is this a clothing item?' gate.

        Runs cheaply in front of the expensive bg-removal + tagging calls.
        Lets us reject cat photos, landscapes, and accidental screenshots with
        a useful error before we burn $0.01+ of Replicate + Claude credits.
        """
        ...
    async def segment_garments(
        self, image_bytes: bytes, hints: list[str] | None = None
    ) -> list[SegmentationMask]:
        """Detect multiple garments in one photo (SAM 2 / instance seg).

        STUB — full implementation deferred. When wired, this enables:
          - "We see 3 items in this photo, add them all?" flow.
          - Fine-grained accessory cutouts (jewelry, glasses) that bg-removal
            today swallows into the silhouette.
          - Per-garment quality_tier routing.

        Until then, returns an empty list. The pipeline falls back to the
        single-garment bg-removal path that exists today.
        """
        ...
    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str | None,
        weather: WeatherSnapshot | None,
        notes: str | None,
        kid_mode: bool,
        style: str | None = None,
    ) -> StylistResult: ...
    async def analyze_gaps(
        self,
        *,
        items: list[dict[str, Any]],
        owner_label: str,
    ) -> GapAnalysisResult: ...
    async def try_on_outfit(
        self,
        *,
        person_image: bytes,
        garments: list[TryonInput],
        body_shape: str | None = None,
    ) -> TryonResult: ...
    async def refine_outfit(
        self,
        *,
        current_items: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        history: list[dict[str, str]],  # [{"role": "user|assistant", "content": "..."}]
        user_message: str,
        destination: str | None,
        mood: str | None,
        style: str | None,
        kid_mode: bool,
    ) -> RefineResult: ...


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
            attributes={
                "neckline": "crew",
                "sleeve_length": "short",
                "fabric": "cotton",
                "fit": "regular",
                "weight_class": "midweight",
            },
        )

    async def remove_background(
        self, image_bytes: bytes, quality_tier: str = "standard"
    ) -> bytes:
        del quality_tier
        return image_bytes

    async def classify_clothing(self, image_bytes: bytes) -> ClothingClassification:
        del image_bytes
        # Stub: always accept so offline dev + tests don't have to mock this.
        return ClothingClassification(
            is_clothing=True,
            confidence=1.0,
            detected_label="stub-accept",
        )

    async def segment_garments(
        self, image_bytes: bytes, hints: list[str] | None = None
    ) -> list[SegmentationMask]:
        del image_bytes, hints
        return []  # stub: SAM 2 wiring deferred

    async def stylist_compose(
        self,
        *,
        candidates: list[dict[str, Any]],
        destination: str,
        mood: str | None,
        weather: WeatherSnapshot | None,
        notes: str | None,
        kid_mode: bool,
        style: str | None = None,
    ) -> StylistResult:
        del style  # stub ignores style — production gateway honours it
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
                rationale_prefix = (
                    f"A {mood} look" if mood else "A versatile look"
                )
                outfits.append(
                    {
                        "items": picked,
                        "rationale": (
                            f"{rationale_prefix} for {destination.replace('_', ' ')}"
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

    async def try_on_outfit(
        self,
        *,
        person_image: bytes,
        garments: list[TryonInput],
        body_shape: str | None = None,
    ) -> TryonResult:
        del body_shape  # stub ignores; production weaves into prompt
        # Stub: just echo the person photo back — lets the UI render something
        # in offline dev without spending Replicate credits.
        return TryonResult(image_bytes=person_image, model_id="stub-tryon-v0")

    async def refine_outfit(
        self,
        *,
        current_items: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        history: list[dict[str, str]],
        user_message: str,
        destination: str | None,
        mood: str | None,
        style: str | None,
        kid_mode: bool,
    ) -> RefineResult:
        del history, destination, mood, kid_mode  # stub ignores
        return RefineResult(
            items=current_items,
            rationale="(stub) outfit unchanged",
            style=style,
            message=f"(stub) ack: {user_message[:80]}",
            model_id="stub-refine-v0",
        )


# Body-shape drape hints for the try-on prompt. nano-banana doesn't reason
# semantically about shape categories, but it does respond to drape language.
# Keep each phrase short — nano-banana follows the first 2-3 prompt clauses
# most reliably.
_BODY_SHAPE_DRAPE = {
    "rectangle": (
        "Render the clothes with a defined waistline; emphasise structure at "
        "the midsection."
    ),
    "hourglass": (
        "Render the clothes tailored to follow the natural waistline; show "
        "balanced volume on top and bottom."
    ),
    "pear": (
        "Render the clothes with a loose, skimming drape over the hips and "
        "a structured fit on top."
    ),
    "apple": (
        "Render the clothes with a softly skimming line over the midsection; "
        "avoid clinging fabrics around the waist."
    ),
    "inverted_triangle": (
        "Render the clothes with looser drape on top and a structured, "
        "fitted line through the bottom."
    ),
    "athletic": (
        "Render the clothes with clean tailored lines that follow the natural "
        "silhouette without adding bulk."
    ),
}


# ---------------------------------------------------------------------------
# Production gateway — Replicate + Anthropic
# ---------------------------------------------------------------------------

# Long enum strings inside the JSON template push past ruff's 100-char limit;
# the prompt is more readable with them on one line so we silence the rule.
# ruff: noqa: E501
_TAGGING_SYSTEM = """\
You are a senior fashion catalogue tagger. Given a single clothing item photo,
return ONLY a JSON object with this exact shape — no markdown, no prose:

{
  "category": "<gender>.<group>.<subcategory>",
  "pattern": "solid|stripe|floral|graphic|plaid|other",
  "colors": [
    {"name": "<color name>", "hex": "#RRGGBB", "weight": 0.0-1.0}
  ],
  "formality": 1-10,
  "seasonality": ["spring"|"summer"|"fall"|"winter", ...],
  "attributes": {
    "neckline": "crew|v|scoop|square|mock|turtleneck|halter|collared|deep_v|off_shoulder|none",
    "sleeve_length": "sleeveless|cap|short|three_quarter|long|extra_long|none",
    "fabric": "cotton|linen|silk|wool|cashmere|denim|leather|suede|knit|synthetic|technical|fur|mesh|other",
    "fit": "skinny|slim|regular|relaxed|oversized|tailored|none",
    "pattern_subtype": "windowpane|gingham|herringbone|paisley|tropical|tartan|polka_dot|abstract|graphic_text|none",
    "embellishments": ["sequins"|"embroidery"|"beading"|"hardware"|"lace"|"none"],
    "weight_class": "lightweight|midweight|heavyweight",
    "waist_rise": "high|mid|low|none",
    "hem_length": "cropped|regular|midi|maxi|none",
    "transparency": "opaque|semi_sheer|sheer"
  },
  "confidence_scores": {
    "category": 0.0-1.0,
    "pattern": 0.0-1.0,
    "color": 0.0-1.0,
    "attributes": 0.0-1.0
  }
}

Category guide:
- <gender> is one of: womens, mens, kids, accessories.
- Use 'accessories' for jewelry, belts, hats, bags, scarves, sunglasses.
- Examples: 'womens.tops.blouse', 'mens.shoes.loafer', 'kids.bottoms.shorts',
  'accessories.jewelry.necklace'.

Formality scale: 1=loungewear, 5=smart-casual, 10=black-tie.

Attribute rules:
- Pick exactly one value per attribute key (except `embellishments`, which is
  a list). Use 'none' when the attribute doesn't apply (e.g. a shoe has no
  neckline).
- 'fabric' is your best visual guess. If unsure between cotton/linen/synthetic,
  pick the closest and lower the attributes confidence score.
- `embellishments`: include every visible decoration. Empty list / ["none"]
  if the item is plain.
- 'weight_class' drives weather-aware styling. A puffer is heavyweight; a
  silk camisole is lightweight.

General rules:
- Return 1-3 dominant colors. Weights sum to ~1.0, sorted by weight descending.
- Hex must be a real 6-digit color present in the photo. No #000000 placeholders.
- If unsure on any field, lower its confidence score. NEVER invent.
- Output ONLY the JSON object. No code fences. No commentary.
"""


_STYLIST_SYSTEM = """\
You are a professional personal stylist working from the user's actual wardrobe.

You receive a JSON payload with: destination, mood, style, weather, notes, kid_mode, and a \
list of `candidates`. Each candidate has: id, slot (top|bottom|dress|shoes|outerwear|accessory), \
category, colors, pattern, formality, seasonality.

`mood` is the wearer's emotional state for this outing. When null, pick a mood that \
fits the destination + style and mention it in the rationale ("a confident, \
modern take on…"). Vocabulary: confident, cozy, edgy, playful, minimal, romantic.

`style` is the aesthetic tradition the user wants to dress within. When set, honour it. \
The vocabulary:
- streetwear: oversized fits, sneakers, graphic/branded pieces, hoodies/bombers, layered.
- minimal: clean lines, monochrome or 2-tone, tailored basics, no logos.
- classic: timeless silhouettes (trench, oxford shirt, denim, loafers), navy/khaki/white.
- preppy: collared shirts, knitwear, pleated skirts/chinos, blazers, loafers.
- bohemian: flowing fabrics, earth tones, layered jewellery, sandals.
- athleisure: technical fabrics, sneakers, joggers/leggings, sweat-set energy.
- avant_garde: asymmetric, sculptural, unconventional pairings, statement pieces.
- smart_casual: blazer-meets-denim, polished sneakers OR loafers, no tie.
If style is null, pick the aesthetic that best matches the candidates + destination.

Compose 2-3 complete outfits. Hard rules:
- Each outfit MUST include shoes.
- Each outfit MUST include either (a) one top + one bottom, OR (b) one dress.
- Never repeat the same item across outfits.
- Respect the weather (temp_c, condition). Cold/rain → outerwear, never sandals.
- Match formality to destination:
  office=5-9, formal_event=8-10, wedding=7-10 (guest attire, never under-dress),
  restaurant=4-8 (UAE skews dressier — Zuma, COYA, Atlantis-level by default),
  date=4-8, religious=5-9 (modest + formal-leaning; cover shoulders/knees,
  prefer long sleeves), brunch=3-7, mall=2-7 (smart-casual UAE default),
  casual=1-6, school=1-5, park=1-4, playground=0-4, beach=0-3 (cover-ups +
  sandals; no shoes that ruin in sand), gym=0-3, travel=2-6.
- Include accessories (jewelry/belt/hat/bag) when they elevate the look.

Fabric + texture compatibility (treat as soft rules; explain any violation in
the rationale):
- Don't mix more than two strongly contrasting textures (silk + cashmere is
  fine; silk + leather + denim + technical is chaos).
- Heavyweight outerwear (puffer, wool coat) needs heavyweight or midweight
  fabrics underneath. Don't pair a silk slip dress with a wool overcoat.
- Lightweight/sheer fabrics call for layering or a higher-formality context
  (silk camisole alone is loungewear; with tailored trousers, dinner).
- Leather + fur in the same outfit = avoid unless requested.

Fit / silhouette compatibility — each candidate carries an `attributes.fit`
value (skinny|slim|regular|relaxed|oversized|tailored). Treat these rules
as soft but call out any violation in the rationale:
- Balance volume: pair oversized/relaxed top with slim/tailored bottom, or
  fitted/tailored top with relaxed/oversized bottom. Avoid oversized-on-
  oversized (drowns the silhouette) and skinny-on-skinny (clings everywhere)
  unless the user explicitly asks for that look.
- Tailored items dress UP a casual piece; relaxed items dress DOWN a formal
  piece. Use this to hit the destination's formality target.
- For workwear / formal destinations (office, formal_event, wedding,
  restaurant), at least ONE item should be tailored or slim — never an
  all-relaxed-and-oversized outfit.
- Athletic / gym destinations: relaxed or slim, never tailored.

Color harmony (output must satisfy AT LEAST ONE):
- Monochrome (all items within one color family, varying tone/value).
- Neutral base + one accent (≤1 saturated colour; rest neutral).
- Complementary pair (e.g. terracotta + teal — used sparingly).
- Analogous trio (e.g. cream, oatmeal, camel).
Never combine 3+ saturated colours from different families. If the only
matching candidates would violate this, surface it in the rationale rather
than silently shipping a clashing outfit.

Output exactly 2-3 outfits, ranked by your confidence (best first).
Never return more than 3.

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

_REFINE_SYSTEM = """\
You are a professional personal stylist refining an outfit through chat.

You receive: the outfit's current items, the user's full closet (`candidates`), \
the conversation so far, and the user's latest message. Update the outfit \
based on what they asked.

Hard rules (same as composition):
- Final outfit MUST include shoes.
- MUST include either (top + bottom) OR a dress.
- Every item_id MUST come from `candidates` — never invent items.
- Keep items the user didn't object to.
- If they ask for something you don't have in the closet, say so and propose \
  the closest substitute from candidates.

Output ONLY this JSON, no markdown:
{
  "outfit": {
    "items": [{"item_id": "<id>", "slot": "<slot>"}, ...],
    "rationale": "<one sentence, second person, why this works now>",
    "style": "<streetwear|minimal|classic|preppy|bohemian|athleisure|avant_garde|smart_casual|null>"
  },
  "message": "<your reply to the user, second person, 1-3 sentences>"
}
"""


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


_GENDER_PREFIX_RE = re.compile(
    r"\b(?:women's|womens|men's|mens|kids)\.",
    re.IGNORECASE,
)


def _strip_gender(description: str | None) -> str | None:
    """Drop "mens.", "womens.", "kids." prefix from a category-style description.

    Try-on bug: Gemini 2.5 image-edit reads item descriptions like
    "navy womens.tops.blouse" and biases toward generating a generic woman
    wearing women's clothes — overriding the actual person in image 1.
    Stripping the gender prefix makes the description gender-neutral so the
    model anchors on the person photo instead. Word-boundary matching so
    "womens." doesn't collide with "mens." substring within it.
    """
    if not description:
        return description
    return _GENDER_PREFIX_RE.sub("", description).strip()


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
        tryon_model: str = (
            "google/nano-banana:"
            "5bdc2c7cd642ae33611d8c33f79615f98ff02509ab8db9d8ec1cc6c36d378fba"
        ),
        bg_removal_model_premium: str | None = None,
    ) -> None:
        from anthropic import AsyncAnthropic

        self._anthropic = AsyncAnthropic(api_key=anthropic_api_key)
        self._replicate_token = replicate_api_token
        self._anthropic_model = anthropic_model
        self._anthropic_vision_model = anthropic_vision_model
        self._bg_removal_model = bg_removal_model
        # If no premium model is configured, fall back to standard — keeps the
        # routing harmless until someone explicitly opts into a premium tier.
        self._bg_removal_model_premium = bg_removal_model_premium or bg_removal_model
        self._clip_model = clip_model
        self._tryon_model = tryon_model
        self._http = httpx.AsyncClient(
            base_url="https://api.replicate.com/v1",
            headers={"Authorization": f"Token {replicate_api_token}"},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        # Replicate's paid tiers support ~10-20 concurrent predictions per
        # account. We allow 3 in flight so:
        #   1. A user-triggered try-on doesn't sit blocked behind a 100-item
        #      batch retag (huge UX win — user wanted to test while seed
        #      retag was running and got stuck waiting 15+ min).
        #   2. Multi-angle renders can stream a few in parallel.
        #   3. We still avoid stampeding the 429 limit. _run_replicate has
        #      retry-with-backoff for the rare burst-throttle case.
        self._replicate_semaphore = asyncio.Semaphore(3)

    async def remove_background(
        self, image_bytes: bytes, quality_tier: str = "standard"
    ) -> bytes:
        """Replicate-based bg removal with two-tier routing.

        - quality_tier="premium" uses self._bg_removal_model_premium (typically
          a slower, higher-quality matting model — MODNet / Cascade-PSP / etc.).
        - quality_tier="standard" (default) uses self._bg_removal_model.

        Degrades to a pass-through on any failure so the rest of the pipeline
        (Claude Vision tagging) still runs. Background removal is a quality
        upgrade, not a correctness requirement — the tagger only needs the
        photo, the user just loses the cutout look on failure.
        """
        if not self._replicate_token:
            return image_bytes
        model = (
            self._bg_removal_model_premium
            if quality_tier == "premium"
            else self._bg_removal_model
        )
        try:
            data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
            _, version = model.split(":", 1)
            result_url = await self._run_replicate(version, {"image": data_url})
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(result_url)
                r.raise_for_status()
                return r.content
        except Exception as exc:
            logger.warning(
                "replicate.bg_removal_failed",
                exc_info=False,
                tier=quality_tier,
                error_type=type(exc).__name__,
                error_msg=str(exc)[:160],
            )
            return image_bytes

    async def classify_clothing(self, image_bytes: bytes) -> ClothingClassification:
        """Zero-shot 'is this clothing?' classifier via Claude Haiku.

        Rationale for using Claude Haiku rather than a Replicate CLIP model:
        we already have Anthropic wired and Haiku is ~$0.0003 / image at
        sub-second latency — meaningfully cheaper end-to-end than spinning
        up a second Replicate prediction (cold-start + queue) for the same
        binary judgment. Haiku is genuinely zero-shot here: the prompt
        enumerates the candidate labels (clothing, person without clothing
        focus, food, animal, landscape, screenshot, document, other).

        On model error / parse failure, fall open (accept) — we'd rather pay
        for one wasted Claude tagging call than reject a real garment. The
        downstream pipeline will degrade gracefully if the photo is genuinely
        un-taggable.
        """
        try:
            media_type = _detect_image_media_type(image_bytes)
            b64 = base64.b64encode(image_bytes).decode()
            content: list[dict[str, Any]] = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Classify this photo. Reply ONLY with JSON: "
                        '{"label": "clothing|footwear|accessory|jewelry|bag|'
                        "person_no_garment_focus|food|animal|landscape|"
                        'screenshot|document|other", "confidence": 0.0-1.0}. '
                        '"clothing", "footwear", "accessory", "jewelry", '
                        '"bag" all count as wearable. Anything else means '
                        "the photo isn't a wearable item the user could "
                        "add to a closet."
                    ),
                },
            ]
            msg = await self._anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=80,
                messages=[{"role": "user", "content": content}],  # type: ignore[typeddict-item]
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
            parsed = _extract_json(text)
            label = str(parsed.get("label", "")).lower().strip()
            confidence = float(parsed.get("confidence", 0.0))
        except Exception as exc:
            logger.warning(
                "clothing_classifier.failed_open",
                error_type=type(exc).__name__,
                error_msg=str(exc)[:160],
            )
            return ClothingClassification(
                is_clothing=True,
                confidence=0.0,
                detected_label="classifier_error",
                reason=None,
            )

        wearable = {"clothing", "footwear", "accessory", "jewelry", "bag"}
        is_clothing = label in wearable
        # Only reject when we're reasonably confident it's NOT clothing.
        # Soft threshold avoids killing legitimate garments shot under
        # weird lighting / unusual angles.
        if not is_clothing and confidence >= 0.7:
            friendly = {
                "person_no_garment_focus": (
                    "This photo focuses on a person rather than a garment. "
                    "Try a flat-lay or close-up of just the item."
                ),
                "food": "This looks like food, not clothing.",
                "animal": "This looks like a pet, not clothing.",
                "landscape": "This looks like a landscape, not clothing.",
                "screenshot": (
                    "This looks like a screenshot. Try a real photo of the item."
                ),
                "document": "This looks like a document, not clothing.",
                "other": (
                    "Couldn't identify a clothing item in this photo. "
                    "Try a clearer shot of just the garment."
                ),
            }
            reason = friendly.get(
                label, "This doesn't look like a clothing item."
            )
            return ClothingClassification(
                is_clothing=False,
                confidence=confidence,
                detected_label=label,
                reason=reason,
            )

        # Either it's wearable, or we're not confident enough to reject —
        # let the rest of the pipeline run.
        return ClothingClassification(
            is_clothing=True,
            confidence=confidence,
            detected_label=label or "uncertain",
        )

    async def segment_garments(
        self, image_bytes: bytes, hints: list[str] | None = None
    ) -> list[SegmentationMask]:
        """Multi-garment detection via Replicate's SAM 2 auto-mask mode.

        Flow:
          1. POST the image to `meta/sam-2` in auto-everything mode. Returns
             a list of mask URLs (binary PNGs at the original resolution).
          2. For each mask, compute its bounding box + area-fraction. Drop
             masks that are too small (<3% of image, almost certainly
             background scraps) or too large (>90%, almost certainly the
             whole frame) or that hug the edge (>80% perimeter overlap —
             usually wall/floor).
          3. Alpha-composite the original image through each kept mask to
             produce a per-garment cutout (RGBA PNG with transparent bg).
          4. Cap at top-6 masks by area so we never overwhelm the user.

        Returns a list of `SegmentationMask` objects. Empty list = SAM 2
        couldn't find any clean regions; caller falls back to single-
        garment bg-removal.

        Cost: ~$0.04 per call (SAM 2 auto-everything mode on Replicate).
        Latency: 10-20s. Reserved for the explicit "scan for multiple items"
        path — not run on every upload.
        """
        del hints  # reserved for future grounded-SAM text prompts

        if not self._replicate_token:
            return []

        import io as _io

        try:
            from PIL import Image as _PILImage

            base_img = _PILImage.open(_io.BytesIO(image_bytes)).convert("RGBA")
            img_w, img_h = base_img.size
            img_area = img_w * img_h
        except Exception as exc:
            logger.warning(
                "sam2.decode_failed",
                error_type=type(exc).__name__,
                error_msg=str(exc)[:160],
            )
            return []

        # meta/sam-2 pinned version. Update via Replicate's model page if it
        # 404s; this version was current as of 2026-Q1.
        sam2_version = (
            "fe97b453a6455861e3bac769b441ca1f1086110da7466dbb65cf1eecfd60dc83"
        )

        try:
            data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
            # `points_per_side` controls how dense the auto-prompt grid is;
            # 16 keeps cost / latency reasonable and is enough to catch
            # 3-6 garments in a typical flat-lay.
            result = await self._run_replicate(
                sam2_version,
                {
                    "image": data_url,
                    "points_per_side": 16,
                    "pred_iou_thresh": 0.86,
                    "stability_score_thresh": 0.92,
                },
                expect="json",
            )
        except Exception as exc:
            logger.warning(
                "sam2.predict_failed",
                error_type=type(exc).__name__,
                error_msg=str(exc)[:160],
            )
            return []

        # Replicate models return masks in a few shapes depending on the
        # checkpoint version. Normalise to a list of URLs.
        mask_urls: list[str] = []
        if isinstance(result, dict):
            individual = result.get("individual_masks") or result.get("masks")
            if isinstance(individual, list):
                mask_urls = [str(u) for u in individual if isinstance(u, str)]
        elif isinstance(result, list):
            mask_urls = [str(u) for u in result if isinstance(u, str)]

        if not mask_urls:
            logger.info("sam2.no_masks")
            return []

        from PIL import Image as _PILImage  # re-import for scope clarity

        kept: list[SegmentationMask] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in mask_urls[:24]:  # hard cap on download volume
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    mask_img = _PILImage.open(_io.BytesIO(r.content)).convert("L")
                except Exception:
                    continue

                if mask_img.size != (img_w, img_h):
                    mask_img = mask_img.resize(
                        (img_w, img_h), _PILImage.Resampling.NEAREST
                    )

                # Bounding box + area filter.
                bbox = mask_img.getbbox()
                if bbox is None:
                    continue
                x0, y0, x1, y1 = bbox
                w, h = x1 - x0, y1 - y0
                area_frac = (w * h) / max(img_area, 1)
                if area_frac < 0.03 or area_frac > 0.90:
                    continue
                # Edge-hugging filter: if the bbox touches three or more
                # frame edges within 8px, it's probably background, not a
                # garment.
                edge_hits = sum(
                    [
                        x0 < 8,
                        y0 < 8,
                        (img_w - x1) < 8,
                        (img_h - y1) < 8,
                    ]
                )
                if edge_hits >= 3:
                    continue

                # Alpha-composite: original RGB + mask as alpha.
                garment = _PILImage.new("RGBA", base_img.size, (0, 0, 0, 0))
                garment.paste(base_img, (0, 0), mask=mask_img)
                cropped = garment.crop(bbox)
                buf = _io.BytesIO()
                cropped.save(buf, format="PNG", optimize=True)

                kept.append(
                    SegmentationMask(
                        mask_bytes=buf.getvalue(),
                        bounding_box=(x0, y0, w, h),
                        label=None,
                    )
                )

        # Largest-first so the most prominent garment is the first row in the
        # mobile preview grid. Cap at 6 — beyond that the picker becomes noise.
        kept.sort(
            key=lambda m: m.bounding_box[2] * m.bounding_box[3],
            reverse=True,
        )
        return kept[:6]

    async def tag_item(self, image_bytes: bytes) -> TagResult:
        tagged = await self._tag_with_claude(image_bytes)
        embedding = await self._embed_clip(image_bytes)
        return TagResult(
            category=tagged["category"],
            pattern=tagged["pattern"],
            colors=tagged["colors"],
            formality=tagged["formality"],
            seasonality=tagged["seasonality"],
            embedding=embedding,
            confidence_scores=ConfidenceScores(root=tagged["confidence_scores"]),
            attributes=tagged["attributes"],
        )

    async def _tag_with_claude(self, image_bytes: bytes) -> dict[str, Any]:
        media_type = _detect_image_media_type(image_bytes)
        b64 = base64.b64encode(image_bytes).decode()
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
            # Bumped from 600 → 1200 to accommodate the new attributes block.
            max_tokens=1200,
            system=_TAGGING_SYSTEM,
            messages=[{"role": "user", "content": content}],  # type: ignore[typeddict-item]
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        parsed = _extract_json(text)
        # Coerce attributes safely. Older models or rare cases may omit it;
        # treat missing → {} and pass through dotted keys.
        attributes = parsed.get("attributes") or {}
        if not isinstance(attributes, dict):
            attributes = {}
        # Normalise common attribute values to lowercase / underscore form.
        attributes = {
            str(k): (
                str(v).lower().strip()
                if isinstance(v, str)
                else [str(x).lower() for x in v]
                if isinstance(v, list)
                else v
            )
            for k, v in attributes.items()
        }
        return {
            "category": parsed["category"],
            "pattern": parsed["pattern"],
            "colors": [_color_from_payload(c) for c in parsed["colors"]],
            "formality": int(parsed["formality"]),
            "seasonality": parsed["seasonality"],
            "attributes": attributes,
            "confidence_scores": {
                k: float(v) for k, v in parsed["confidence_scores"].items()
            },
        }

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
        mood: str | None,
        weather: WeatherSnapshot | None,
        notes: str | None,
        kid_mode: bool,
        style: str | None = None,
    ) -> StylistResult:
        model = "claude-haiku-4-5" if kid_mode else self._anthropic_model
        system = _STYLIST_SYSTEM + (_STYLIST_KID_SUFFIX if kid_mode else "")
        payload = {
            "destination": destination,
            "mood": mood,
            "style": style,
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

    async def try_on_outfit(
        self,
        *,
        person_image: bytes,
        garments: list[TryonInput],
        body_shape: str | None = None,
    ) -> TryonResult:
        """Real virtual try-on via IDM-VTON, chained per garment.

        WHY IDM-VTON (not nano-banana):
        google/nano-banana is a general image-edit model. With a person photo
        + garment photos as inputs it tends to GENERATE a new person wearing
        the clothes rather than EDIT the input photo — identity drift was
        severe in production (rendered a stranger every time). IDM-VTON is
        purpose-built virtual try-on: it segments the person's clothing,
        masks the target region, and inpaints the new garment while
        preserving face, hair, body, and pose. Identity preservation is
        the model's training objective, not a prompt-coaxing hope.

        Multi-garment strategy:
        IDM-VTON renders one garment per call. We chain — top first, output
        of that becomes the new "person" image for the bottom, etc. We
        stop after upper/lower garments because shoes and accessories
        don't have reliable try-on support in this model class.

        Cost / latency:
        ~$0.06 + ~15-25s per garment. A typical 2-garment outfit (top +
        bottom) renders in ~30-50s for ~$0.12. Heavier than nano-banana
        but the renders are actually you.
        """
        del body_shape  # IDM-VTON doesn't take a drape hint; identity preservation handles fit
        if not self._replicate_token:
            raise RuntimeError("REPLICATE_API_TOKEN required for try-on")
        if not garments:
            raise ValueError("at least one garment required")

        # IDM-VTON garment categories. We only render slots the model
        # actually handles well; shoes/accessories/jewelry get skipped here
        # (they're still part of the outfit data, just not rendered).
        slot_to_category = {
            "top": "upper_body",
            "outerwear": "upper_body",
            "bottom": "lower_body",
            "dress": "dresses",
        }
        renderable = [g for g in garments if g.slot in slot_to_category]
        if not renderable:
            raise RuntimeError(
                "no renderable garments — IDM-VTON supports top/outerwear/"
                "bottom/dress only"
            )

        # Render order: dress first (full body), then top, then outerwear
        # (layered over top), then bottom. Each call uses the previous call's
        # output as the new "person" image.
        order = {"dress": 0, "top": 1, "outerwear": 2, "bottom": 3}
        renderable.sort(key=lambda g: order.get(g.slot, 99))

        _, version = self._tryon_model.split(":", 1)
        current_person = person_image

        for garment in renderable:
            current_person = await self._idm_vton_step(
                version=version,
                person_bytes=current_person,
                garment=garment,
                category=slot_to_category[garment.slot],
            )

        return TryonResult(
            image_bytes=current_person,
            model_id=self._tryon_model.split(":")[0],
        )

    async def _idm_vton_step(
        self,
        *,
        version: str,
        person_bytes: bytes,
        garment: TryonInput,
        category: str,
    ) -> bytes:
        """One IDM-VTON prediction: render the person wearing one garment."""
        person_url = (
            "data:image/jpeg;base64," + base64.b64encode(person_bytes).decode()
        )
        garm_url = (
            f"data:{_detect_image_media_type(garment.image_bytes)};base64,"
            + base64.b64encode(garment.image_bytes).decode()
        )
        # IDM-VTON's `garment_des` is a short text description of the garment;
        # we feed the gender-stripped category + colour hint.
        desc = _strip_gender(garment.description) or garment.slot

        result_url = await self._run_replicate(
            version,
            {
                "human_img": person_url,
                "garm_img": garm_url,
                "garment_des": desc,
                "category": category,
                # Auto-mask + auto-crop give the best identity preservation
                # without us having to ship a SAM segmentation pipeline.
                "is_checked": True,
                "is_checked_crop": True,
                "denoise_steps": 30,
            },
        )
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.get(result_url)
            r.raise_for_status()
            return r.content

    async def refine_outfit(
        self,
        *,
        current_items: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        history: list[dict[str, str]],
        user_message: str,
        destination: str | None,
        mood: str | None,
        style: str | None,
        kid_mode: bool,
    ) -> RefineResult:
        """One-turn refinement: read the chat history, return revised outfit + reply."""
        model = "claude-haiku-4-5" if kid_mode else self._anthropic_model
        # We pack the outfit/closet/context into the system prompt as a JSON
        # block so the conversation messages stay as conversation messages
        # (better for Claude's chat-tuned behaviour than embedding everything
        # in a single user turn).
        context = {
            "current_outfit_items": current_items,
            "candidates": candidates,
            "destination": destination,
            "mood": mood,
            "style": style,
            "kid_mode": kid_mode,
        }
        system = _REFINE_SYSTEM + "\n\nCONTEXT:\n" + json.dumps(context)

        # Build message array from history + the new user turn.
        messages: list[dict[str, Any]] = []
        for h in history:
            role = h.get("role")
            content = h.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        msg = await self._anthropic.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=messages,  # type: ignore[arg-type]  # SDK's MessageParam TypedDict
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        parsed = _extract_json(text)
        outfit_data = parsed.get("outfit") or {}
        return RefineResult(
            items=outfit_data.get("items") or current_items,
            rationale=outfit_data.get("rationale"),
            style=outfit_data.get("style") or style,
            message=str(parsed.get("message", "")).strip()
            or "Updated. Tap to render the try-on again.",
            model_id=model,
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
            bg_removal_model_premium=s.replicate_bg_removal_model_premium,
            clip_model=s.replicate_clip_model,
            tryon_model=s.replicate_tryon_model,
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
            tryon_model=s.replicate_tryon_model,
        )


