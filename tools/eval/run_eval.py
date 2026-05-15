"""Score the configured ModelGateway over a labelled JSONL dataset.

Usage:
    uv run python -m tools.eval.run_eval --dataset tools/eval/datasets/sample.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.model_gateway import ModelGateway, get_model_gateway


@dataclass
class EvalRecord:
    image_path: Path
    category: str
    pattern: str
    primary_color: str
    formality: int
    seasonality: list[str]


def _load(dataset_path: Path) -> list[EvalRecord]:
    records: list[EvalRecord] = []
    base = dataset_path.parent
    for line in dataset_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        records.append(
            EvalRecord(
                image_path=(base / row["image"]).resolve(),
                category=row["category"],
                pattern=row["pattern"],
                primary_color=row["primary_color"],
                formality=int(row["formality"]),
                seasonality=list(row["seasonality"]),
            )
        )
    return records


def _category_top_level(label: str) -> str:
    parts = label.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else label


async def _score_one(
    gateway: ModelGateway, rec: EvalRecord, missing_ok: bool
) -> dict[str, Any] | None:
    if not rec.image_path.exists():
        if missing_ok:
            return None
        raise FileNotFoundError(rec.image_path)
    image_bytes = rec.image_path.read_bytes()
    pred = await gateway.tag_item(image_bytes)
    return {
        "category_exact": pred.category == rec.category,
        "category_topish": _category_top_level(pred.category) == _category_top_level(rec.category),
        "pattern": pred.pattern == rec.pattern,
        "formality_within_2": abs(pred.formality - rec.formality) <= 2,
        "season_overlap": bool(set(pred.seasonality) & set(rec.seasonality)),
        "category_true": rec.category,
        "category_pred": pred.category,
    }


async def run(dataset: Path, missing_ok: bool) -> dict[str, Any]:
    gateway = get_model_gateway()
    records = _load(dataset)
    results = []
    for rec in records:
        res = await _score_one(gateway, rec, missing_ok=missing_ok)
        if res is not None:
            results.append(res)

    if not results:
        return {
            "scored": 0,
            "warning": "no images found on disk; add files under tools/eval/images/",
        }

    def rate(key: str) -> float:
        return statistics.fmean(1.0 if r[key] else 0.0 for r in results)

    per_category: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        per_category[_category_top_level(r["category_true"])].append(r["category_exact"])

    return {
        "scored": len(results),
        "skipped_missing_images": len(records) - len(results),
        "category_exact_accuracy": round(rate("category_exact"), 3),
        "category_top_level_accuracy": round(rate("category_topish"), 3),
        "pattern_accuracy": round(rate("pattern"), 3),
        "formality_within_2_accuracy": round(rate("formality_within_2"), 3),
        "seasonality_overlap_rate": round(rate("season_overlap"), 3),
        "per_category_exact_accuracy": {
            k: round(sum(v) / len(v), 3) for k, v in sorted(per_category.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any image file is missing on disk",
    )
    parser.add_argument("--out", type=Path, help="Write a JSON summary to this path")
    args = parser.parse_args()

    summary = asyncio.run(run(args.dataset, missing_ok=not args.strict))
    print(json.dumps(summary, indent=2))
    if args.out:
        args.out.write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
