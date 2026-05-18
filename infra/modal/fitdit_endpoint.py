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

# Build the container image. PyTorch/diffusers pinned because FitDiT is
# sensitive to those versions; everything else stays loose so gradio can
# pull whatever pydantic/fastapi it wants without a resolver conflict.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        # Versions from FitDiT's upstream requirements.txt, plus extras
        # for the parts we use (DWPose, HumanParsing) which import onnx
        # at runtime. The official req.txt pins are tight but we loosen
        # a few to avoid resolver conflicts with our other deps.
        "torch==2.4.0",
        "torchvision==0.19.0",
        "accelerate==0.31.0",
        "diffusers==0.31.0",
        "transformers==4.39.3",
        "numpy<2",
        "scikit-image",
        "huggingface_hub>=0.25,<0.27",
        "onnxruntime",         # required by FitDiT for DWPose + parsing
        "opencv-python-headless",
        "matplotlib",
        "einops",
        "safetensors",
        "Pillow>=10",
        "scipy",
        # FitDiT's gradio_sd3.py has a top-level `import gradio`. We don't
        # use the UI, but the import has to succeed to reach the
        # FitDiTGenerator class definition below it.
        "gradio",
    )
    .run_commands(f"git clone {FITDIT_REPO} /opt/fitdit")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .pip_install("hf-transfer")
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
        "steps": 20                  # diffusion steps; FitDiT default
      }

    Response JSON (200):
      { "image_b64": "<base64 jpeg>", "duration_ms": int }
    Response JSON (4xx/5xx):
      { "error": "<message>" }
    """
    import base64
    import sys
    import time

    from fastapi.responses import JSONResponse

    started = time.monotonic()

    person_b64 = payload.get("person_image")
    garm_b64 = payload.get("garment_image")
    # Upstream FitDiT uses "Upper-body" / "Lower-body" / "Dresses" as its
    # category labels. We accept the underscore form (matching IDM-VTON's
    # API) and translate.
    category_in = payload.get("category", "upper_body")
    category_map = {
        "upper_body": "Upper-body",
        "lower_body": "Lower-body",
        "dresses": "Dresses",
    }
    if not person_b64 or not garm_b64:
        return JSONResponse(
            {"error": "person_image and garment_image required"},
            status_code=400,
        )
    if category_in not in category_map:
        return JSONResponse(
            {"error": "category must be upper_body|lower_body|dresses"},
            status_code=400,
        )
    category = category_map[category_in]
    steps = int(payload.get("steps", 20))
    # Higher resolution = better detail + identity preservation.
    # FitDiT only accepts these three values.
    resolution = payload.get("resolution", "768x1024")
    if resolution not in ("768x1024", "1152x1536", "1536x2048"):
        return JSONResponse(
            {"error": "resolution must be 768x1024|1152x1536|1536x2048"},
            status_code=400,
        )
    image_scale = float(payload.get("image_scale", 2.0))

    # Lazy-import FitDiT. The upstream repo isn't PyPI-packaged so we add
    # its checkout dir to sys.path. The entry-point class lives in
    # `gradio_sd3.FitDiTGenerator` (see the upstream README).
    sys.path.insert(0, "/opt/fitdit")
    try:
        from gradio_sd3 import FitDiTGenerator  # type: ignore[import-not-found]
    except Exception as exc:
        # Diagnostic: list what IS available, so a cached-image mismatch is
        # obvious from the error response alone.
        import os

        diag = {
            "error": f"failed to import FitDiT: {exc}",
            "sys_path_head": sys.path[:5],
            "opt_fitdit_exists": os.path.exists("/opt/fitdit"),
            "opt_fitdit_files": (
                sorted(os.listdir("/opt/fitdit"))[:10]
                if os.path.exists("/opt/fitdit")
                else "N/A"
            ),
        }
        try:
            import gradio as _g

            diag["gradio_version"] = getattr(_g, "__version__", "unknown")
        except Exception as g_exc:
            diag["gradio_import_error"] = str(g_exc)
        return JSONResponse(diag, status_code=500)

    # Build generator once per container (Modal caches the function's
    # closure across calls).
    global _generator  # noqa: PLW0603
    if "_generator" not in globals() or _generator is None:
        try:
            _generator = FitDiTGenerator(
                model_root=f"{MODELS_DIR}/FitDiT",
                offload=False,
                aggressive_offload=False,
                device="cuda:0",
                with_fp16=False,
            )
        except Exception as exc:
            return JSONResponse(
                {"error": f"failed to init FitDiT generator: {exc}"},
                status_code=500,
            )

    # FitDiT expects FILE PATHS, not PIL Image objects. The methods call
    # `Image.open(vton_img)` internally, which requires a path or a
    # file-like object — a raw PIL.Image will AttributeError. Save the
    # uploaded bytes to tempfiles, pass the paths.
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as pf:
        pf.write(base64.b64decode(person_b64))
        person_path = pf.name
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as gf:
        gf.write(base64.b64decode(garm_b64))
        garment_path = gf.name

    try:
        # Step 1: auto-generate the inpaint mask from the person photo.
        # generate_mask returns (im_dict, pose_image) where im_dict is the
        # Gradio ImageEditor dict — we pass it back to `process` as-is.
        mask_dict, pose_image = _generator.generate_mask(
            vton_img=person_path,
            category=category,
            offset_top=0,
            offset_bottom=0,
            offset_left=0,
            offset_right=0,
        )

        # FitDiT contract mismatch: generate_mask returns pose_image as a
        # PIL.Image, but process() does `Image.fromarray(pose_image)` on
        # it. Convert back to numpy so process can re-wrap.
        import numpy as np

        if hasattr(pose_image, "size"):  # it's a PIL Image
            pose_image = np.array(pose_image)

        # Step 2: render the garment into the masked region. FitDiT's
        # resolution arg is a string in the supported-resolutions set;
        # "768x1024" is the fastest tier.
        images = _generator.process(
            vton_img=person_path,
            garm_img=garment_path,
            pre_mask=mask_dict,
            pose_image=pose_image,
            n_steps=steps,
            image_scale=image_scale,
            seed=-1,
            num_images_per_prompt=1,
            resolution=resolution,
        )
    except Exception as exc:
        import traceback

        return JSONResponse(
            {
                "error": f"inference failed: {type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc().splitlines()[-12:],
            },
            status_code=500,
        )
    finally:
        # Cleanup temp files even on success — they're written under /tmp
        # which is per-container but still polite to clean.
        import os

        for p in (person_path, garment_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    if not images:
        return JSONResponse({"error": "model returned no images"}, status_code=500)
    result = images[0] if isinstance(images, list) else images

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
