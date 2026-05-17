# Try-on scale: bypassing the Replicate semaphore

**Status:** Draft architecture plan. Not yet implemented.

## The bottleneck

`ProductionGateway._replicate_semaphore` (currently set to `Semaphore(3)`)
serializes Replicate predictions per worker process. With one worker
process the entire app can have **3 IDM-VTON renders in flight at a time
across all users**. A typical 2-garment try-on takes ~50s. So peak
throughput today:

```
3 concurrent renders × (60s / 50s per render) ≈ 3.6 renders/min
```

This works for one user testing. It does NOT work for a family
(Ayman + Nathalie + kids) all trying outfits at once, and it definitely
does not work for a real consumer launch.

The semaphore exists because Replicate's account-level rate limits
(varies by tier) penalize 429 retries and Replicate's per-prediction
cold-start can stack into stampedes. The semaphore is a pragmatic
floor, not a scale strategy.

## Three layers of the fix, in order

### Layer 1 — Immediate: split the worker pools (1 hour, no infra change)

Today both ingest jobs (Claude Vision + bg-removal) and try-on jobs
(IDM-VTON) share the same Arq worker process and the same
`ProductionGateway` instance — they fight for the same 3 semaphore
slots. A 100-item closet retag will starve user try-ons for ~30 min.

**Fix:** Run two Arq workers with separate function whitelists:

```
arq app.services.ingest_worker.IngestWorkerSettings   # only ingest_item
arq app.services.ingest_worker.TryonWorkerSettings    # only tryon_outfit
                                                       # + compose_outfit_image
```

Each worker has its own ProductionGateway instance with its own
semaphore. Configure:
- Ingest worker: `Semaphore(2)` — slow batch traffic, doesn't need bursts
- Try-on worker: `Semaphore(5)` — user-facing, prioritize throughput

Net throughput: 5 concurrent try-ons + 2 concurrent ingests = **~6
renders/min** for try-on alone, with no infrastructure change.

Trade-off: doubles the worker process count. Memory cost ~200MB extra.

### Layer 2 — Short term: self-host IDM-VTON on Modal Labs (1-2 days)

Replicate's serialized account semaphore is fundamentally a shared
queue. Self-hosting IDM-VTON gives us dedicated GPU(s) with our own
concurrency knobs.

**Why Modal Labs over RunPod / EC2 / SageMaker:**
- Python-native: deploy with a decorator, not a container build
- Per-second billing on GPU (~$2/hr for A100, $0.50/hr for L40S)
- Autoscale to zero: idle cost = $0
- Cold start ~2-5s for warm pool, ~30s from zero
- Same model weights, same outputs as Replicate

**Migration steps:**
1. Add `infra/modal/tryon_endpoint.py`:
   - `@app.function(gpu="L40S", scaledown_window=300)` decorator
   - Pull IDM-VTON weights from HF Hub on first call
   - Pin to the same checkpoint as Replicate's `cuuupid/idm-vton`
   - Cache weights in a Modal Volume so cold starts skip the download
2. Deploy: `modal deploy infra/modal/tryon_endpoint.py`
3. Modal returns a URL like `https://aymanbfl--virtual-stylist-tryon.modal.run`
4. Add `MODAL_TRYON_ENDPOINT` to `services/api/.env`
5. New `ModalTryonGateway` class in `app/services/model_gateway.py`
   mirroring the existing `ProductionGateway.try_on_outfit` interface
6. Feature-flag the swap: `TRYON_BACKEND=modal|replicate` so we can
   roll back instantly

Throughput after migration (with autoscale max=10 GPUs):
```
10 GPUs × (60s / 50s) ≈ 12 renders/min sustained
peak burst: 10 simultaneous renders (no queue at all)
```

Cost at this scale: ~$0.05–0.10 per render (Modal L40S
~$0.50/hr ÷ ~10 renders/hr). Replicate charges ~$0.06–0.12 per render
for the same call. **Self-hosting is roughly cost-neutral** at scale
while giving us the concurrency knob.

### Layer 3 — Medium term: switch to a faster multi-garment model (1 week)

IDM-VTON renders one garment per call. For multi-garment outfits we
chain (top → bottom → outerwear), so 3 garments = 3 sequential
renders. Newer models do multi-garment in one pass:

- **FitDiT** (ByteDance, 2025) — multi-garment in one pass, ~15-20s
  for 2 garments, identity preservation comparable to IDM-VTON
- **Leffa** (Tencent, 2025) — single-pass, slightly less identity-stable
- **OOTDiffusion** dc-mode — half-body or full-body in one pass,
  established but quality slightly behind FitDiT

**Migration steps:**
1. Smoke test each candidate via `scripts/smoke_tryon.py` against
   Ayman's actual base photo + a real 3-garment outfit
2. Eyeball the outputs for identity preservation, garment fit, hand
   rendering
3. Pick the winner; deploy on the same Modal endpoint (just a
   different `@app.function`)
4. Update `replicate_tryon_model` → `modal_tryon_endpoint` + model id

Per-render time drops from ~75s → ~20s. Combined with Layer 2
parallelism (10 GPUs):
```
10 GPUs × (60s / 20s) ≈ 30 renders/min sustained
```

That's enough for a soft consumer launch (a few hundred concurrent
users).

## Per-user fairness

Once we have parallelism we also need per-user rate limits, otherwise
one user with a 10-outfit batch monopolizes the GPU pool. Add to the
try-on request handler:

```python
# Per-user limit: 3 concurrent renders + 30/min max
@limiter.limit("30/minute", key_func=user_or_ip)
```

Plus a per-user in-flight counter in Redis to prevent fan-out abuse:

```python
INFLIGHT_KEY = f"tryon:inflight:{user.id}"
inflight = await redis.incr(INFLIGHT_KEY)
if inflight > 3:
    await redis.decr(INFLIGHT_KEY)
    raise HTTPException(429, "Too many renders in flight. Wait ~60s.")
try:
    # ...kick off the job...
finally:
    await redis.decr(INFLIGHT_KEY)
```

## Decision summary

| Stage | Effort | Time-to-deploy | Throughput | Risk |
|---|---|---|---|---|
| **Layer 1: split worker pools** | 1 hour | same day | 6 renders/min | low — just config |
| **Layer 2: Modal self-host** | 1-2 days | end of week | 12 renders/min | medium — new infra, but feature-flagged |
| **Layer 3: FitDiT model swap** | 1 week | within 2 weeks | 30 renders/min | medium — needs identity-preservation eyeball test |

Recommend: **ship Layer 1 today, plan Layer 2 for end of week, evaluate
Layer 3 once Modal is stable.**

## Out of scope (for now)

- Multi-region GPU pools (not needed until we have international users)
- ML model fine-tuning on Ayman / Nathalie's photos (would help identity
  preservation further but introduces per-user training cost)
- Switching to a CPU-only matting + per-garment overlay approach (faster
  but doesn't preserve the "AI generated this on your photo" feel)
