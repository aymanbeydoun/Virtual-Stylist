# Modal Labs — FitDiT try-on deployment

Self-hosted virtual try-on on Modal Labs, autoscaled GPU function backing the
production `try_on_outfit` flow. Replaces Replicate IDM-VTON when
`MODAL_TRYON_ENDPOINT` is set in `.env`.

## Why Modal (vs Replicate)

| | Replicate IDM-VTON (current default) | Modal FitDiT (this) |
|---|---|---|
| Per-garment latency | ~17s | ~5s (paper) |
| 3-garment outfit | ~75s | ~15-20s |
| Concurrency model | Account-wide serialized semaphore | Per-function autoscaler 0→10 GPUs |
| Cost (idle) | $0 (no idle) | $0 (scaledown to zero after 5 min) |
| Cost (per render) | ~$0.04 | ~$0.003-0.005 |
| Identity preservation | Best in class | Comparable (SOTA paper benchmark) |

## One-time setup (~10 min)

1. **Create a Modal account.** New accounts get $30 free credit, enough for
   ~10,000 renders.
   ```
   open https://modal.com/signup
   ```
2. **Install Modal locally:**
   ```
   pip install modal
   modal token new
   ```
   (Opens your browser to authenticate. Token is stored at `~/.modal.toml`.)
3. **Pre-populate the weights Volume** (one-off, ~5-10 min download to
   Modal):
   ```
   cd infra/modal
   modal run fitdit_endpoint.py::download_weights
   ```
   This pulls FitDiT weights from HuggingFace into a Modal Volume so
   subsequent cold-starts skip the multi-GB download.
4. **Deploy the endpoint:**
   ```
   modal deploy fitdit_endpoint.py
   ```
   Modal prints the public URL, eg
   `https://aymanbeydoun--virtual-stylist-tryon-predict.modal.run`.
5. **Wire it into the API** — add to `services/api/.env`:
   ```
   MODAL_TRYON_ENDPOINT=https://aymanbeydoun--virtual-stylist-tryon-predict.modal.run
   ```
6. **Restart API + worker:**
   ```
   cd services/api
   pkill -f "uvicorn app.main" ; pkill -f "arq app.services.ingest"
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
   uv run arq app.services.ingest_worker.WorkerSettings &
   ```

That's it. The worker auto-routes try-on jobs to Modal when the env var is
set. To roll back to Replicate IDM-VTON, comment out the env line and
restart.

## Verifying it works

After deploy, smoke-test against your real base photo + a garment:

```
cd services/api
uv run python scripts/smoke_tryon.py
```

Output goes to `services/api/smoke_tryon_output/result.jpg`. Open it — the
person should still look like you (face / body / pose preserved). If yes,
the swap is live. Production try-ons will use FitDiT automatically.

## Monitoring

```
modal app logs virtual-stylist-tryon       # tail logs
modal app stats virtual-stylist-tryon      # request counts, latency
```

## Rolling back

Either:
- Remove `MODAL_TRYON_ENDPOINT` from `.env` → worker falls back to IDM-VTON
- `modal app stop virtual-stylist-tryon` → kills the function entirely

The `ProductionGateway` keeps Replicate IDM-VTON as the fallback path
indefinitely — no code change needed to switch back.

## Cost model

L40S GPU billed per-second on Modal:
- Cold start (weights from Volume): ~30s
- Warm render: ~5s/garment
- Idle (no requests): $0
- Sustained load: ~$1.84/hr × (active seconds) / 3600

For one user generating 10 outfits/day at 3 garments each:
- 30 garments × 5s × 1/3600 hr × $1.84 = **~$0.077/day**

For a family of 4 each doing 10 outfits/day:
- 120 garments × 5s × 1/3600 hr × $1.84 = **~$0.31/day**

Even at consumer-launch scale (1,000 active users), Modal cost stays under
$80/day, well below the per-render Replicate cost.

## Architecture notes

- `infra/modal/fitdit_endpoint.py` is the only Modal-deployable file. It
  pins PyTorch/diffusers versions to FitDiT's known-good set, clones the
  FitDiT repo into the container image at build time, and lazy-loads the
  generator on first request (cached for warm calls).
- The endpoint is a single FastAPI POST `/predict` mounted via Modal's
  `@modal.fastapi_endpoint` decorator. JSON in, JSON out, base64 images.
- Garments chain just like the Replicate path: top → bottom → outerwear.
  Each step takes ~5s on FitDiT, so a 3-garment outfit lands in ~15s.
- The Modal Volume named `fitdit-weights` persists FitDiT weights across
  deploys. If you want to test a different FitDiT checkpoint or fork,
  override `FITDIT_HF_WEIGHTS` in `fitdit_endpoint.py` and re-run
  `download_weights`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `modal: command not found` | Modal not installed | `pip install modal` |
| 401 from endpoint | Token expired | `modal token new` |
| First call hangs > 60s | Cold start downloading weights from HF (not the Volume) | Run `download_weights` first |
| 500 with "failed to import FitDiT" | FitDiT repo layout changed upstream | Check upstream README, update import path in `predict()` |
| Renders look identity-drifted | Wrong FitDiT checkpoint or category mismatch | Re-run smoke_tryon.py, compare to Replicate IDM-VTON baseline |
