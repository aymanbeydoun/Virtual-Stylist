"""IDM-VTON virtual try-on on Modal Labs (D2).

Replaces FitDiT in the Modal deployment. Same Modal autoscale + per-second
billing, but uses yisol's IDM-VTON model — the proven identity-preserving
try-on we already validated on Replicate.

Why this is the right answer:
  - FitDiT was faster but had garment-rendering quality issues on non-
    product-photo inputs (the kind of photos seeded from Pexels).
  - IDM-VTON gracefully handles model-on-garment photos and produces
    cleaner garment renders.
  - Moving IDM-VTON OFF Replicate onto our own Modal GPUs eliminates the
    serialized account-level semaphore that was bottlenecking us.

Performance budget:
  - Per-garment forward pass: ~15-25s on L40S
  - Full 3-garment outfit chained: ~45-75s
  - Cold-start from zero: ~60-90s (weights cached in Volume)
  - Concurrency: autoscale 0->10 simultaneous renders

Deploy:
  cd infra/modal
  modal run idm_vton_endpoint.py::download_weights   # one-off, ~15 min
  modal deploy idm_vton_endpoint.py

Modal prints the public URL. Paste it into services/api/.env as:
  MODAL_TRYON_ENDPOINT=https://aymanbeydoun--virtual-stylist-tryon-idm-predict.modal.run

The same `_modal_tryon_step` in ProductionGateway works against this
endpoint — endpoint-agnostic request/response schema (person_image,
garment_image, category, returns image_b64).

Cost (May 2026 Modal pricing):
  - L40S on-demand: ~$1.84/hr
  - Per-garment render at 20s: ~$0.010
  - 3-garment outfit: ~$0.030
  - Idle: $0 (scaledown to zero after 5 min)
"""
from __future__ import annotations

import io

import modal

APP_NAME = "virtual-stylist-tryon-idm"
WEIGHTS_VOLUME = modal.Volume.from_name("idm-vton-weights", create_if_missing=True)
MODELS_DIR = "/models"

IDM_VTON_REPO = "https://github.com/yisol/IDM-VTON.git"
# yisol publishes the full IDM-VTON checkpoint set at this HF repo.
# Includes the custom SDXL inpaint pipeline, IP-Adapter image encoder,
# DensePose checkpoint, OpenPose checkpoint, and humanparsing model.
IDM_VTON_HF = "yisol/IDM-VTON"


# Build the container image. detectron2 (DensePose) is the tricky dep —
# it builds against a specific torch+CUDA combo. We pin torch 2.0.1+cu118
# which matches the pre-built detectron2 wheel.
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "libgl1", "libglib2.0-0", "build-essential", "wget")
    .pip_install(
        "torch==2.0.1",
        "torchvision==0.15.2",
        index_url="https://download.pytorch.org/whl/cu118",
    )
    .pip_install(
        # IDM-VTON's own deps from yisol's repo.
        "diffusers==0.25.0",
        "transformers==4.36.2",
        "accelerate==0.25.0",
        "huggingface_hub>=0.20,<0.25",
        "safetensors",
        "Pillow",
        "numpy<2",
        "opencv-python-headless",
        "scipy",
        "einops",
        "matplotlib",
        "scikit-image",
        "scikit-learn",
        "onnxruntime",
        # Detectron2 pre-built wheel matching torch 2.0.1 + cu118.
        # See https://detectron2.readthedocs.io/en/latest/tutorials/install.html
        "detectron2 @ git+https://github.com/facebookresearch/detectron2.git@v0.6",
        # IDM-VTON uses spaces decorator at module level — we don't need
        # the runtime but the import has to succeed.
        "spaces",
        # detectron2's densepose module imports `av` (PyAV) for its video
        # dataset code, even on image-only inference paths. Without it the
        # apply_net import fails. Pin to a known-good build.
        "av",
        # FastAPI for the Modal endpoint wrapper.
        "fastapi[standard]",
    )
    .run_commands(
        f"git clone {IDM_VTON_REPO} /opt/idm-vton",
        # yisol's repo references './configs/densepose_*.yaml' relative to
        # gradio_demo/ but those configs aren't included in the repo —
        # they come from detectron2's projects/DensePose. Pull them
        # separately and drop them in the expected path.
        (
            "git clone --depth=1 --filter=blob:none --sparse "
            "https://github.com/facebookresearch/detectron2.git /tmp/d2 && "
            "cd /tmp/d2 && git sparse-checkout set projects/DensePose/configs && "
            "mkdir -p /opt/idm-vton/gradio_demo/configs && "
            "cp -r /tmp/d2/projects/DensePose/configs/* "
            "/opt/idm-vton/gradio_demo/configs/ && "
            "rm -rf /tmp/d2"
        ),
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTHONPATH": "/opt/idm-vton"})
    .pip_install("hf-transfer")
)

app = modal.App(APP_NAME, image=image)


@app.function(
    gpu="L40S",
    timeout=300,
    scaledown_window=300,
    max_containers=10,
    volumes={MODELS_DIR: WEIGHTS_VOLUME},
)
@modal.fastapi_endpoint(method="POST")
def predict(payload: dict) -> dict:
    """Single-garment IDM-VTON try-on.

    Request JSON (same schema as the FitDiT endpoint):
      {
        "person_image": "<base64 jpeg>",
        "garment_image": "<base64 jpeg/png>",
        "category": "upper_body" | "lower_body" | "dresses",
        "garment_description": "<short text>",
        "steps": 30
      }

    Response JSON:
      { "image_b64": "<base64 jpeg>", "duration_ms": int }
    """
    import base64
    import os
    import sys
    import time

    from fastapi.responses import JSONResponse

    started = time.monotonic()

    person_b64 = payload.get("person_image")
    garm_b64 = payload.get("garment_image")
    category = payload.get("category", "upper_body")
    garment_des = payload.get("garment_description") or "garment"
    steps = int(payload.get("steps", 30))

    if not person_b64 or not garm_b64:
        return JSONResponse(
            {"error": "person_image and garment_image required"},
            status_code=400,
        )
    if category not in ("upper_body", "lower_body", "dresses"):
        return JSONResponse(
            {"error": "category must be upper_body|lower_body|dresses"},
            status_code=400,
        )

    # Lazy-import IDM-VTON. yisol's app.py loads heavy global state at
    # import time (model + pipelines), so we wrap in try/except and pull
    # the work into our generator-init helper.
    sys.path.insert(0, "/opt/idm-vton")
    sys.path.insert(0, "/opt/idm-vton/gradio_demo")

    try:
        global _idm_pipe, _idm_openpose, _idm_parser  # noqa: PLW0603
        if "_idm_pipe" not in globals() or _idm_pipe is None:
            # The IDM-VTON repo's ckpt/ dir tracks ONNX/PKL files via git-LFS
            # which `git clone` doesn't pull by default. We already have all
            # the equivalents in the Modal Volume — symlink them into the
            # repo's expected ckpt/ path.
            symlink_diag = _ensure_ckpt_symlinks()
            try:
                _idm_pipe, _idm_openpose, _idm_parser = _init_idm_vton()
            except Exception as init_exc:
                import traceback

                return JSONResponse(
                    {
                        "error": f"init failed: {type(init_exc).__name__}: {init_exc}",
                        "symlinks": symlink_diag,
                        "traceback": traceback.format_exc().splitlines()[-15:],
                    },
                    status_code=500,
                )
    except Exception as exc:
        import traceback

        return JSONResponse(
            {
                "error": f"failed to init IDM-VTON: {type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc().splitlines()[-20:],
            },
            status_code=500,
        )

    try:
        from PIL import Image

        person_img = Image.open(io.BytesIO(base64.b64decode(person_b64))).convert("RGB")
        garm_img = Image.open(io.BytesIO(base64.b64decode(garm_b64))).convert("RGB")
        result_img = _run_idm_vton(
            person_img=person_img,
            garm_img=garm_img,
            category=category,
            garment_des=garment_des,
            steps=steps,
        )
    except Exception as exc:
        import traceback

        return JSONResponse(
            {
                "error": f"inference failed: {type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc().splitlines()[-20:],
            },
            status_code=500,
        )

    out_buf = io.BytesIO()
    result_img.save(out_buf, format="JPEG", quality=92)
    out_b64 = base64.b64encode(out_buf.getvalue()).decode()

    del os  # silence unused-import linter

    return {
        "image_b64": out_b64,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _ensure_ckpt_symlinks() -> dict:
    """Wire the Volume's checkpoints into the IDM-VTON repo's expected paths.

    yisol's code hard-codes relative paths like
    `./ckpt/humanparsing/parsing_atr.onnx`. The git clone doesn't include
    those LFS files but our HF snapshot of yisol/IDM-VTON does. Symlink
    the Volume dirs into /opt/idm-vton/ckpt/.

    Returns a diagnostic dict showing what each symlink resolves to plus
    file sizes — surfaces the cause of any "InvalidProtobuf" errors.
    """
    import os
    import shutil

    # Yisol's relative paths assume cwd = gradio_demo/, so symlink there.
    # We mirror to /opt/idm-vton/ckpt/ too for any code that looks at the
    # repo root.
    repo_ckpt = "/opt/idm-vton/gradio_demo/ckpt"
    _alias_ckpt = "/opt/idm-vton/ckpt"
    volume_root = f"{MODELS_DIR}/IDM-VTON"
    diag: dict[str, str] = {}

    # CRITICAL: the upstream IDM-VTON repo SHIPS a `ckpt/` directory
    # containing git-LFS POINTER files (tiny ~133-byte text stubs). The
    # `git clone` in the image build pulls those pointer files, NOT the
    # real weights. We have to NUKE the existing /opt/idm-vton/ckpt
    # before symlinking — otherwise onnxruntime tries to parse the LFS
    # pointer as ONNX and fails with InvalidProtobuf.
    #
    # Same hazard applies to /opt/idm-vton/gradio_demo/ckpt — both must
    # be wiped before symlink.
    for path in (_alias_ckpt, repo_ckpt):
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)

    os.makedirs(repo_ckpt, exist_ok=True)
    # Mirror gradio_demo/ckpt at repo-root since yisol's run_parsing.py
    # computes Path(__file__).parents[2] → /opt/idm-vton/, then appends
    # 'ckpt/humanparsing/...'. So the path that matters for humanparsing
    # is /opt/idm-vton/ckpt/. The gradio_demo/ckpt path matters for
    # apply_net.py which uses cwd-relative paths.
    os.symlink(repo_ckpt, _alias_ckpt)
    for subdir in ("humanparsing", "openpose", "densepose"):
        target = os.path.join(repo_ckpt, subdir)
        source = os.path.join(volume_root, subdir)
        if not os.path.exists(source):
            diag[subdir] = f"MISSING source {source}"
            continue
        # Remove existing target (could be the git-cloned LFS-pointer dir).
        if os.path.islink(target):
            os.unlink(target)
        elif os.path.exists(target):
            shutil.rmtree(target, ignore_errors=True)
        os.symlink(source, target)
        # Sanity-check first file size — LFS pointers are ~133 bytes, real
        # weights are MBs.
        try:
            children = os.listdir(target)
            sizes = {c: os.path.getsize(os.path.join(target, c)) for c in children[:3]}
            diag[subdir] = f"symlinked → {source} files={sizes}"
        except OSError as exc:
            diag[subdir] = f"symlink ok but listdir failed: {exc}"

    return diag


def _init_idm_vton():  # noqa: ANN202
    """Load all IDM-VTON model weights + return the inference primitives.

    Heavy — only call once per container. The returned tuple is cached as
    a global so subsequent requests skip the load.
    """
    import torch
    from diffusers import AutoencoderKL, DDPMScheduler
    from transformers import (
        AutoTokenizer,
        CLIPImageProcessor,
        CLIPTextModel,
        CLIPTextModelWithProjection,
        CLIPVisionModelWithProjection,
    )

    from preprocess.humanparsing.run_parsing import Parsing  # type: ignore[import-not-found]
    from preprocess.openpose.run_openpose import OpenPose  # type: ignore[import-not-found]
    from src.tryon_pipeline import (  # type: ignore[import-not-found]
        StableDiffusionXLInpaintPipeline as TryonPipeline,
    )
    from src.unet_hacked_garmnet import (  # type: ignore[import-not-found]
        UNet2DConditionModel as UNet2DConditionModel_ref,
    )
    from src.unet_hacked_tryon import (  # type: ignore[import-not-found]
        UNet2DConditionModel,
    )

    base_path = f"{MODELS_DIR}/IDM-VTON"

    unet = UNet2DConditionModel.from_pretrained(
        base_path, subfolder="unet", torch_dtype=torch.float16
    )
    tokenizer_one = AutoTokenizer.from_pretrained(
        base_path, subfolder="tokenizer", use_fast=False
    )
    tokenizer_two = AutoTokenizer.from_pretrained(
        base_path, subfolder="tokenizer_2", use_fast=False
    )
    noise_scheduler = DDPMScheduler.from_pretrained(base_path, subfolder="scheduler")
    text_encoder_one = CLIPTextModel.from_pretrained(
        base_path, subfolder="text_encoder", torch_dtype=torch.float16
    )
    text_encoder_two = CLIPTextModelWithProjection.from_pretrained(
        base_path, subfolder="text_encoder_2", torch_dtype=torch.float16
    )
    image_encoder = CLIPVisionModelWithProjection.from_pretrained(
        base_path, subfolder="image_encoder", torch_dtype=torch.float16
    )
    vae = AutoencoderKL.from_pretrained(base_path, subfolder="vae", torch_dtype=torch.float16)
    UNet_Encoder = UNet2DConditionModel_ref.from_pretrained(
        base_path, subfolder="unet_encoder", torch_dtype=torch.float16
    )

    parsing_model = Parsing(0)
    openpose_model = OpenPose(0)

    UNet_Encoder.requires_grad_(False)
    image_encoder.requires_grad_(False)
    vae.requires_grad_(False)
    unet.requires_grad_(False)
    text_encoder_one.requires_grad_(False)
    text_encoder_two.requires_grad_(False)

    pipe = TryonPipeline.from_pretrained(
        base_path,
        unet=unet,
        vae=vae,
        feature_extractor=CLIPImageProcessor(),
        text_encoder=text_encoder_one,
        text_encoder_2=text_encoder_two,
        tokenizer=tokenizer_one,
        tokenizer_2=tokenizer_two,
        scheduler=noise_scheduler,
        image_encoder=image_encoder,
        torch_dtype=torch.float16,
    )
    pipe.unet_encoder = UNet_Encoder
    pipe.to("cuda")
    pipe.unet_encoder.to("cuda")
    openpose_model.preprocessor.body_estimation.model.to("cuda")

    return pipe, openpose_model, parsing_model


def _run_idm_vton(
    *,
    person_img: object,
    garm_img: object,
    category: str,
    garment_des: str,
    steps: int,
) -> object:
    """One IDM-VTON inference. Mirrors yisol's `start_tryon` in HF Space."""
    import sys
    from typing import List

    import numpy as np
    import torch
    from detectron2.data.detection_utils import (  # type: ignore[import-not-found]
        _apply_exif_orientation,
        convert_PIL_to_numpy,
    )
    from PIL import Image
    from torchvision import transforms
    from torchvision.transforms.functional import to_pil_image

    sys.path.insert(0, "/opt/idm-vton")
    sys.path.insert(0, "/opt/idm-vton/gradio_demo")
    import apply_net  # type: ignore[import-not-found]
    from utils_mask import get_mask_location  # type: ignore[import-not-found]

    tensor_transfrom = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5]),
        ]
    )

    pipe = _idm_pipe  # noqa: F821 — set in predict()
    openpose_model = _idm_openpose  # noqa: F821
    parsing_model = _idm_parser  # noqa: F821

    garm_img = garm_img.convert("RGB").resize((768, 1024))
    human_img = person_img.convert("RGB").resize((768, 1024))

    # Auto-mask via OpenPose keypoints + human parsing.
    keypoints = openpose_model(human_img.resize((384, 512)))
    model_parse, _ = parsing_model(human_img.resize((384, 512)))
    mask, mask_gray = get_mask_location("hd", category, model_parse, keypoints)
    mask = mask.resize((768, 1024))

    mask_gray = (1 - transforms.ToTensor()(mask)) * tensor_transfrom(human_img)
    mask_gray = to_pil_image((mask_gray + 1.0) / 2.0)
    del mask_gray  # not returned; freed for memory

    # DensePose for body shape conditioning. apply_net uses relative paths
    # like `./configs/...` and `./ckpt/...` — chdir into the gradio_demo
    # subdir so those resolve. Restore cwd in finally.
    import os as _os

    prev_cwd = _os.getcwd()
    _os.chdir("/opt/idm-vton/gradio_demo")
    try:
        human_img_arg = _apply_exif_orientation(human_img.resize((384, 512)))
        human_img_arg = convert_PIL_to_numpy(human_img_arg, format="BGR")

        args = apply_net.create_argument_parser().parse_args(
            (
                "show",
                "./configs/densepose_rcnn_R_50_FPN_s1x.yaml",
                "./ckpt/densepose/model_final_162be9.pkl",
                "dp_segm",
                "-v",
                "--opts",
                "MODEL.DEVICE",
                "cuda",
            )
        )
        pose_img = args.func(args, human_img_arg)
    finally:
        _os.chdir(prev_cwd)
    pose_img = pose_img[:, :, ::-1]
    pose_img = Image.fromarray(pose_img).resize((768, 1024))

    prompt = "model is wearing " + garment_des
    negative_prompt = "monochrome, lowres, bad anatomy, worst quality, low quality"
    device = "cuda"

    with torch.no_grad(), torch.cuda.amp.autocast(), torch.inference_mode():
        (
            prompt_embeds,
            negative_prompt_embeds,
            pooled_prompt_embeds,
            negative_pooled_prompt_embeds,
        ) = pipe.encode_prompt(
            prompt,
            num_images_per_prompt=1,
            do_classifier_free_guidance=True,
            negative_prompt=negative_prompt,
        )

        prompt_c = "a photo of " + garment_des
        if not isinstance(prompt_c, List):
            prompt_c = [prompt_c] * 1
        neg_prompt_list = [negative_prompt] * 1
        (prompt_embeds_c, _, _, _) = pipe.encode_prompt(
            prompt_c,
            num_images_per_prompt=1,
            do_classifier_free_guidance=False,
            negative_prompt=neg_prompt_list,
        )

        pose_tensor = tensor_transfrom(pose_img).unsqueeze(0).to(device, torch.float16)
        garm_tensor = tensor_transfrom(garm_img).unsqueeze(0).to(device, torch.float16)
        generator = torch.Generator(device).manual_seed(42)
        images = pipe(
            prompt_embeds=prompt_embeds.to(device, torch.float16),
            negative_prompt_embeds=negative_prompt_embeds.to(device, torch.float16),
            pooled_prompt_embeds=pooled_prompt_embeds.to(device, torch.float16),
            negative_pooled_prompt_embeds=negative_pooled_prompt_embeds.to(
                device, torch.float16
            ),
            num_inference_steps=steps,
            generator=generator,
            strength=1.0,
            pose_img=pose_tensor,
            text_embeds_cloth=prompt_embeds_c.to(device, torch.float16),
            cloth=garm_tensor,
            mask_image=mask,
            image=human_img,
            height=1024,
            width=768,
            ip_adapter_image=garm_img.resize((768, 1024)),
            guidance_scale=2.0,
        )[0]

    del np  # silence unused

    return images[0]


@app.function(
    image=image,
    volumes={MODELS_DIR: WEIGHTS_VOLUME},
    timeout=2400,  # full IDM-VTON weight set is ~12 GB
)
def download_weights() -> str:
    """One-off: pre-populate the Volume with IDM-VTON checkpoints.

    Run with: modal run idm_vton_endpoint.py::download_weights
    """
    import os

    from huggingface_hub import snapshot_download

    target = f"{MODELS_DIR}/IDM-VTON"
    if os.path.exists(target) and len(os.listdir(target)) > 5:
        return f"weights already present at {target}"

    path = snapshot_download(
        repo_id=IDM_VTON_HF,
        local_dir=target,
        max_workers=8,
    )
    WEIGHTS_VOLUME.commit()
    return f"downloaded to {path}"


if __name__ == "__main__":  # pragma: no cover
    print("Deploy with `modal deploy idm_vton_endpoint.py` — see header docstring.")
