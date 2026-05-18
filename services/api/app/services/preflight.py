"""Cheap preflight gate that runs before the expensive Claude/Replicate calls.

Goals:
  1. Reject obviously-blurry photos (Laplacian variance under threshold).
  2. Reject obvious garbage uploads (corrupt files surfaced via Pillow).
  3. Surface actionable errors back to the user instead of mysteriously
     marking items 'failed' deep in the pipeline.

What this is NOT: a clothing-vs-not classifier. That would need a small
CLIP model. Today the prompt itself handles "this isn't clothing" by
returning low confidence; we'll add a real clothing-gate model when the
quality bar requires it.

All checks run inside the worker on bytes we already have in memory — no
extra API calls, no extra latency. ~5ms per image.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter


@dataclass
class PreflightResult:
    ok: bool
    reason: str | None = None  # human-readable, surfaced in mobile UI
    blur_score: float = 0.0  # Laplacian variance; higher = sharper


# Empirically calibrated: a phone-shot of a t-shirt typically scores 200+;
# motion-blurred / out-of-focus / heavily compressed photos drop below 80.
# We use 60 to leave headroom for compressed Unsplash test images.
_MIN_BLUR_SCORE = 60.0

# Minimum dimensions. Anything smaller than this is almost certainly a
# thumbnail or stock placeholder, not a real photo.
_MIN_DIM = 256


def preflight_check(raw: bytes) -> PreflightResult:
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        return PreflightResult(
            ok=False, reason=f"Couldn't decode image ({type(exc).__name__})"
        )

    w, h = img.size
    if w < _MIN_DIM or h < _MIN_DIM:
        return PreflightResult(
            ok=False,
            reason=f"Photo is too small ({w}x{h}). Need at least {_MIN_DIM}x{_MIN_DIM}.",
        )

    # Convert to greyscale + compute Laplacian variance.
    # Pillow doesn't have a Laplacian filter built in, but FIND_EDGES is a
    # close-enough proxy for our blur-vs-sharp gate.
    grey = img.convert("L")
    edges = grey.filter(ImageFilter.FIND_EDGES)
    arr = np.array(edges, dtype=np.float32)
    score = float(arr.var())
    if score < _MIN_BLUR_SCORE:
        return PreflightResult(
            ok=False,
            reason=(
                "Photo looks too blurry to tag reliably. Try better lighting, "
                "hold the camera still, or use a different shot."
            ),
            blur_score=score,
        )

    return PreflightResult(ok=True, blur_score=score)
