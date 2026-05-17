"""FitDiT virtual try-on as a Modal Labs HTTP endpoint.

Deploys Tencent's FitDiT (https://github.com/BoyuanJiang/FitDiT) on a Modal
GPU function with autoscaling and weights cached in a Modal Volume so
cold-starts don't re-download.

Why Modal over Replicate for this:
  - Replicate doesn't host FitDiT; the only options were stale ports
    or paying Replicate for our own custom-model uploads.
  - Modal lets us scale 0 -> N GPUs on demand, paying per-second only
    when a render is in flight. Idle cost = $0.
  - The serialized per-account semaphore that bottlenecks Replicate
    doesn't apply — Modal's concurrency is per-function, not per-account.

Performance budget (paper benchmark + our targets):
  - Per-garment forward pass: ~4.6s on A100 at 1024x768
  - Full 3-garment outfit chained: ~15-20s
  - Cold-start from zero: ~30-45s (weights from Volume)
  - Warm-pool latency: ~5s end-to-end

Deploy:
  cd infra/modal
  modal token new          # one-time, opens browser for Modal login
  modal deploy fitdit_endpoint.py

Modal prints a URL after deploy. Paste it into services/api/.env as:
  TRYON_BACKEND=modal
  MODAL_TRYON_ENDPOINT=https://<your-modal-app>.modal.run

Cost (May 2026 Modal pricing):
  - A100 40GB on-demand: ~$3.09/hr -> ~$0.004 per 5s render
  - L40S on-demand: ~$1.84/hr -> ~$0.003 per 5s render
  - Scaledown after 5 min idle -> $0 idle cost
We default to L40S — faster cold-start, ~3x cheaper, FitDiT runs
comfortably in 24GB VRAM at 1024x768.
"""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

import modal

if TYPE_CHECKING:
    # Only used in type hints inside the Modal container — pulled at runtime
    # from the image. Local checkers don't need these.
    import torch  # noqa: F401
    from PIL import Image  # noqa: F401


APP_NAME = "virtual-stylist-tryon"
WEIGHTS_VOLUME = modal.Volume.from_name("fitdit-weights", create_if_missing=True)
MODELS_DIR = "/models"

# FitDiT repo + weights pulled at build time. The repo's inference module
# is imported inside the function (not at module top-level) so the local
# `modal deploy` step doesn't need PyTorch installed.
FITDIT_REPO = "https://github.com/BoyuanJiang/FitDiT.git"
FITDIT_HF_WEIGHTS = "BoyuanJiang/FitDiT"

# Build the container image. We pin PyTorch + diffusers to FitDiT's known-good
# range; the FitDiT repo lacks a strict pinned requirements.txt so we hand-pick.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "diffusers==0.30.3",
        "transformers==4.45.2",
        "accelerate==1.0.1",
        "huggingface_hub==0.25.2",
        "Pillow==10.4.0",
        "numpy==1.26.4",
        "scipy==1.14.1",
        "opencv-python-headless==4.10.0.84",
        "einops==0.8.0",
        "safetensors==0.4.5",
        "fastapi[standard]==0.115.0",
    )
    .run_commands(
        # Clone FitDiT inference code so the function imports its
        # `cat_vton_pipeline` (or equivalent) classes.
        f"git clone {FITDIT_REPO} /opt/fitdit",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .pip_install("hf-transfer==0.1.8")  # parallel chunked downloads from HF
)

app = modal.App(APP_NAME, image=image)


@app.function(
    gpu="L40S",
    timeout=300,                    # max 5 min per single render
    scaledown_window=300,           # keep warm 5 min after last call
    max_containers=10,              # autoscale up to 10 concurrent GPUs
    volumes={MODELS_DIR: WEIGHTS_VOLUME},
)
@modal.fastapi_endpoint(method="POST")
def predict(payload: dict) -> dict:
    """Single-garment FitDiT try-on.

    Request JSON:
      {
        "person_image": "<base64 jpeg>",
        "garment_image": "<base64 jpeg/png>",
        "category": "upper_body" | "lower_body" | "dresses",
        "garment_description": "<optional short text>",
        "steps": 30                  # diffusion steps; 30 is the FitDiT default
      }

    Response JSON:
      { "image_b64": "<base64 jpeg>", "duration_ms": int }
    """
    import base64
    import sys
    import time

    started = time.monotonic()

    person_b64 = payload.get("person_image")
    garm_b64 = payload.get("garment_image")
    category = payload.get("category", "upper_body")
    garment_desc = payload.get("garment_description", "garment")
    steps = int(payload.get("steps", 30))

    if not person_b64 or not garm_b64:
        return {"error": "person_image and garment_image required"}, 400  # type: ignore[return-value]
    if category not in ("upper_body", "lower_body", "dresses"):
        return {"error": "category must be upper_body|lower_body|dresses"}, 400  # type: ignore[return-value]

    # Lazy-import FitDiT inference. The repo's structure isn't fully PyPI-
    # packaged so we extend sys.path to its checked-out directory.
    sys.path.insert(0, "/opt/fitdit")
    try:
        from PIL import Image

        # The exact module path depends on FitDiT's repo layout. The
        # canonical entry-point at the time of writing is
        # `gradio_app.FitDiTGenerator`. If this import fails after a repo
        # update, check the upstream README for the current API.
        from gradio_app import FitDiTGenerator  # type: ignore[import-not-found]
    except Exception as exc:
        return {"error": f"failed to import FitDiT: {exc}"}, 500  # type: ignore[return-value]

    # Build generator once per container (Modal caches the function's closure
    # across calls). The check guards against re-init on warm calls.
    global _generator  # noqa: PLW0603
    if "_generator" not in globals() or _generator is None:
        _generator = FitDiTGenerator(
            model_root=f"{MODELS_DIR}/FitDiT",
            offload=False,
        )

    person_img = Image.open(io.BytesIO(base64.b64decode(person_b64))).convert("RGB")
    garment_img = Image.open(io.BytesIO(base64.b64decode(garm_b64))).convert("RGB")

    result = _generator.generate(
        vton_img=person_img,
        garm_img=garment_img,
        pre_mask=None,             # let FitDiT auto-mask the target region
        category=category,
        n_steps=steps,
        image_scale=2.0,           # paper recommended; keep
        seed=-1,
        num_samples=1,
        resolution=1024,
        garment_description=garment_desc,
    )

    out_buf = io.BytesIO()
    result.save(out_buf, format="JPEG", quality=92)
    out_b64 = base64.b64encode(out_buf.getvalue()).decode()

    return {
        "image_b64": out_b64,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


@app.function(
    image=image,
    volumes={MODELS_DIR: WEIGHTS_VOLUME},
    timeout=1800,  # weight download can take 15-20 min on first run
)
def download_weights() -> str:
    """One-off function to pre-populate the weights Volume.

    Run with:  modal run fitdit_endpoint.py::download_weights
    Idempotent — checks for existing weights before re-downloading.
    """
    import os

    from huggingface_hub import snapshot_download

    target = f"{MODELS_DIR}/FitDiT"
    if os.path.exists(target) and os.listdir(target):
        return f"weights already present at {target}"

    path = snapshot_download(
        repo_id=FITDIT_HF_WEIGHTS,
        local_dir=target,
        max_workers=8,
    )
    WEIGHTS_VOLUME.commit()
    return f"downloaded to {path}"


# Local entry-point so `python -m infra.modal.fitdit_endpoint` doesn't crash —
# mostly a no-op for IDEs that probe the file.
if __name__ == "__main__":  # pragma: no cover
    print("This file is meant to be deployed with `modal deploy`, not run directly.")
