"""Benchmark Replicate bg-removal candidates side-by-side.

The "premium" bg-removal tier in `app/config.py::replicate_bg_removal_model_premium`
defaults to the same model as standard so the app doesn't break on a fresh
deploy. To actually pick a premium model you need to run real images through
each candidate, eyeball the cutouts, and pick the one with the best
hair/jewelry edges and texture preservation.

This script does that comparison:

  uv run scripts/benchmark_bg_removal.py \\
      --images storage/raw/**/*.jpg \\
      --limit 8 \\
      --out bench_output

It writes:
  bench_output/
    summary.csv                          # one row per (image, model) with timing
    summary.md                           # markdown report with file links
    {model-slug}/
      {original-filename}.png            # the cutout

Then open the model-slug folders side-by-side in Finder / VS Code and
decide. Set REPLICATE_BG_REMOVAL_MODEL_PREMIUM in `.env` to the winner.

Cost: roughly $0.005-0.04 per (image, model) depending on the model. With
the default 8 images x 4 models that's ~$0.30-1.50. The script prints a
running tally so there are no surprises.

Run with:
  cd services/api && uv run scripts/benchmark_bg_removal.py [--help]

Required env:
  REPLICATE_API_TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import glob
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

# Default candidate set. These are the models we recommend evaluating for the
# premium tier. Each entry is (display_name, replicate_slug_with_version,
# estimated_per_run_usd). Versions pinned for reproducibility — if any of these
# returns 404, check Replicate's model page for the current version hash.
DEFAULT_CANDIDATES: list[tuple[str, str, float]] = [
    (
        "851-labs-standard",
        "851-labs/background-remover:"
        "a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc",
        0.005,
    ),
    (
        "cjwbw-rembg",
        "cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46af3cd861d029289ce14a73dabea3f6e0",
        0.005,
    ),
    (
        "pollinations-modnet",
        "pollinations/modnet:da7d45f3b836795f945f221fc0b01a6dad8328007e20c138ae4f9d36ec3e5cf6",
        0.020,
    ),
    (
        "lucataco-rembg-fast",
        "lucataco/rembg:fb8af171cfa1616ddcf1242c093f9c46af3cd861d029289ce14a73dabea3f6e0",
        0.005,
    ),
]


@dataclass
class BenchResult:
    image_name: str
    model_name: str
    output_path: str | None
    duration_s: float
    bytes_out: int
    error: str | None


async def _run_model(
    client: httpx.AsyncClient,
    image_bytes: bytes,
    version: str,
    timeout_s: float,
) -> tuple[bytes, float]:
    """Submit one prediction and poll until it finishes. Returns (output_bytes, seconds)."""
    started = time.monotonic()
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    create = await client.post(
        "/predictions",
        json={"version": version, "input": {"image": data_url}},
        timeout=30.0,
    )
    create.raise_for_status()
    pred = create.json()
    poll_url = pred["urls"]["get"]

    while True:
        if time.monotonic() - started > timeout_s:
            raise TimeoutError(f"prediction timed out after {timeout_s}s")
        await asyncio.sleep(2.0)
        r = await client.get(poll_url, timeout=30.0)
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        if status == "succeeded":
            output = body.get("output")
            if isinstance(output, list):
                output = output[0]
            if not output:
                raise RuntimeError("succeeded but no output URL")
            async with httpx.AsyncClient(timeout=60.0) as raw_client:
                img = await raw_client.get(output)
                img.raise_for_status()
                return img.content, time.monotonic() - started
        if status in ("failed", "canceled"):
            raise RuntimeError(f"replicate prediction {status}: {body.get('error')}")


async def bench_one(
    client: httpx.AsyncClient,
    image_path: Path,
    model_name: str,
    model_slug: str,
    out_dir: Path,
    timeout_s: float,
) -> BenchResult:
    raw = image_path.read_bytes()
    _, version = model_slug.split(":", 1)
    target_dir = out_dir / model_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / (image_path.stem + ".png")

    try:
        cutout, elapsed = await _run_model(client, raw, version, timeout_s)
    except Exception as exc:
        return BenchResult(
            image_name=image_path.name,
            model_name=model_name,
            output_path=None,
            duration_s=0.0,
            bytes_out=0,
            error=f"{type(exc).__name__}: {str(exc)[:160]}",
        )
    target_path.write_bytes(cutout)
    return BenchResult(
        image_name=image_path.name,
        model_name=model_name,
        output_path=str(target_path),
        duration_s=elapsed,
        bytes_out=len(cutout),
        error=None,
    )


def _write_summary(results: list[BenchResult], out_dir: Path, cost_map: dict[str, float]) -> None:
    csv_path = out_dir / "summary.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "model", "seconds", "bytes_out", "est_cost_usd", "error"])
        for r in results:
            w.writerow(
                [
                    r.image_name,
                    r.model_name,
                    f"{r.duration_s:.2f}",
                    r.bytes_out,
                    f"{cost_map.get(r.model_name, 0.0):.4f}",
                    r.error or "",
                ]
            )

    # Markdown report grouped by image so you can scan rows top-to-bottom.
    md = out_dir / "summary.md"
    with md.open("w") as f:
        f.write("# Background removal benchmark\n\n")
        f.write("Open each model folder in Finder / VS Code and pick the winner.\n")
        f.write("Set `REPLICATE_BG_REMOVAL_MODEL_PREMIUM` in `.env` accordingly.\n\n")
        per_image: dict[str, list[BenchResult]] = {}
        for r in results:
            per_image.setdefault(r.image_name, []).append(r)
        for img_name, rows in per_image.items():
            f.write(f"## `{img_name}`\n\n")
            f.write("| Model | Seconds | KB out | Est cost | Output |\n")
            f.write("|---|---:|---:|---:|---|\n")
            for r in rows:
                cost = cost_map.get(r.model_name, 0.0)
                if r.error:
                    f.write(
                        f"| {r.model_name} | — | — | — | ⚠ {r.error} |\n"
                    )
                else:
                    rel = Path(r.output_path or "").relative_to(out_dir)
                    f.write(
                        f"| {r.model_name} | {r.duration_s:.2f} | "
                        f"{r.bytes_out / 1024:.1f} | "
                        f"${cost:.4f} | `{rel}` |\n"
                    )
            f.write("\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--images",
        default="storage/raw/**/*.jpg",
        help="Glob of input images. Default: storage/raw/**/*.jpg",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Cap number of images to keep the cost sane. Default: 5.",
    )
    parser.add_argument(
        "--out",
        default="bench_output",
        help="Output directory. Default: bench_output",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-prediction timeout in seconds. Default: 120.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help=(
            "Override the candidate list. Format: name=replicate_slug:version. "
            "Eg: --models my-pick=cjwbw/rembg:fb8af1..."
        ),
    )
    args = parser.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN not set", file=sys.stderr)
        return 1

    paths = sorted(Path(p) for p in glob.glob(args.images, recursive=True))[: args.limit]
    if not paths:
        print(f"ERROR: no images matched {args.images!r}", file=sys.stderr)
        return 1

    if args.models:
        candidates: list[tuple[str, str, float]] = []
        for spec in args.models:
            if "=" not in spec:
                print(f"ERROR: bad --models entry {spec!r}", file=sys.stderr)
                return 1
            name, slug = spec.split("=", 1)
            candidates.append((name, slug, 0.005))
    else:
        candidates = DEFAULT_CANDIDATES

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cost_map = {name: cost for name, _, cost in candidates}
    total_predictions = len(paths) * len(candidates)
    est_cost = sum(cost_map.values()) * len(paths)
    print(f"Running {total_predictions} predictions on {len(paths)} images")
    print(f"Estimated cost: ${est_cost:.2f}")
    print(f"Writing results to {out_dir}/\n")

    results: list[BenchResult] = []
    async with httpx.AsyncClient(
        base_url="https://api.replicate.com/v1",
        headers={"Authorization": f"Token {token}"},
    ) as client:
        # Serial across models to avoid stampeding Replicate's rate limiter.
        # Within a model, also serial: the goal is clean, comparable timings.
        for name, slug, _cost in candidates:
            print(f"  Model: {name}")
            for path in paths:
                print(f"    {path.name} … ", end="", flush=True)
                r = await bench_one(
                    client, path, name, slug, out_dir, args.timeout
                )
                if r.error:
                    print(f"FAIL ({r.error[:80]})")
                else:
                    print(f"{r.duration_s:.1f}s")
                results.append(r)

    _write_summary(results, out_dir, cost_map)
    print(f"\nSummary written to {out_dir}/summary.md")
    print("Open the model subdirectories side-by-side and pick the winner.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
