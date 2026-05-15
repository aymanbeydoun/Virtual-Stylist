# Tagging Eval Harness

This is the dataset format and runner we use to track CV tagging quality over
time. The harness runs the configured `ModelGateway` over a labelled set of
images and reports accuracy per attribute.

## Dataset format

Each dataset is a JSONL file. One line per labelled item:

```jsonl
{"image": "datasets/images/blouse_navy_01.jpg", "category": "womens.tops.blouse", "pattern": "stripe", "primary_color": "navy", "formality": 6, "seasonality": ["spring","fall"]}
```

Required fields:

| field            | type        | notes                                             |
|------------------|-------------|---------------------------------------------------|
| `image`          | string      | path relative to `tools/eval/` |
| `category`       | string      | dot-separated taxonomy (`womens.tops.blouse`)     |
| `pattern`        | string      | one of `solid stripe floral graphic plaid other`  |
| `primary_color`  | string      | named color the human labeller chose              |
| `formality`      | int 0–10    | 0 = athleisure, 10 = black tie                    |
| `seasonality`    | string list | subset of `spring summer fall winter`             |

Bring your own images. Don't commit unlicensed product photos — use either
shots you took yourself or items from a permissively-licensed dataset
(DeepFashion / Fashionpedia for research use).

## Running

```bash
cd services/api
PYTHONPATH=../.. uv run python -m tools.eval.run_eval \
  --dataset ../../tools/eval/datasets/sample.jsonl
```

Add `--backend anthropic` to evaluate the production stylist; default is the
stub so this works without API keys in CI.

## Quality bar (Phase 2 exit gate)

- ≥90% top-1 category accuracy on a 500-item internal set across men/women/kids.
- ≥85% on pattern.
- Per-category breakdown so we can see where the model is weak.

Tracked in dashboards by exporting `eval_summary.json` to BigQuery from CI.
