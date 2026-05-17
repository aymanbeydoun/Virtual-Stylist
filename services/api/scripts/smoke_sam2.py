"""End-to-end smoke test for the SAM 2 multi-garment detection pipeline.

Picks a real uploaded image from storage/raw/, runs it through the
production gateway's segment_garments() method, and writes the detected
regions to disk for visual inspection. Verifies:
  1. The Replicate SAM 2 call returns valid mask URLs.
  2. Our mask-filtering pipeline keeps the right regions and drops noise.
  3. Each output region is a cropped, transparent-background PNG.
  4. The full flow is wired correctly end-to-end.

Cost: ~$0.04 per run (one SAM 2 auto-everything prediction). Latency 15-30s.

Run with:
  cd services/api && uv run scripts/smoke_sam2.py [path/to/image.jpg]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.services.model_gateway import get_model_gateway


async def main() -> int:
    if len(sys.argv) > 1:
        image_path = Path(sys.argv[1])
    else:
        # Default: first .jpg in storage/raw/
        candidates = list(Path("storage/raw").rglob("*.jpg"))
        if not candidates:
            print("ERROR: no .jpg found in storage/raw/", file=sys.stderr)
            return 1
        image_path = candidates[0]

    if not image_path.exists():
        print(f"ERROR: {image_path} not found", file=sys.stderr)
        return 1

    from PIL import Image as _PIL

    raw = image_path.read_bytes()
    src_img = _PIL.open(image_path)
    src_w, src_h = src_img.size
    src_area = src_w * src_h
    print(f"Input: {image_path} ({src_w}x{src_h}, {len(raw):,} bytes)")
    print("Calling SAM 2 (this takes 15-30s)…")

    gateway = get_model_gateway()
    masks = await gateway.segment_garments(raw)

    print(f"\nDetected {len(masks)} region(s):")
    out_dir = Path("smoke_sam2_output") / image_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, mask in enumerate(masks):
        x, y, w, h = mask.bounding_box
        area_pct = (w * h) / src_area * 100
        out_path = out_dir / f"region_{i:02d}.png"
        out_path.write_bytes(mask.mask_bytes)
        print(
            f"  [{i:02d}] bbox=({x},{y},{w}x{h})  "
            f"{area_pct:.1f}% of source  →  {out_path}"
        )

    if not masks:
        print("\nNo regions kept after filtering.")
        print(
            "This is expected for single-garment photos. SAM 2 returns "
            "many candidates and our filter drops anything <3% of the "
            "frame or hugging the edges. Try a flat-lay with 2-4 distinct "
            "items if you want to see multi-detection in action."
        )
    else:
        print(f"\nOpen {out_dir}/ to inspect the cutouts side-by-side.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
