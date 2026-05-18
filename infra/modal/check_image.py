"""One-off Modal function to verify what's actually installed in the image."""
import modal

# Mirror the EXACT image definition from fitdit_endpoint.py
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "diffusers==0.30.3",
        "transformers==4.45.2",
        "accelerate==1.0.1",
        "huggingface_hub>=0.25,<0.27",
        "Pillow>=10",
        "numpy<2",
        "scipy",
        "opencv-python-headless",
        "einops",
        "safetensors",
        "gradio",
    )
    .run_commands("git clone https://github.com/BoyuanJiang/FitDiT.git /opt/fitdit")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .pip_install("hf-transfer")
)

app = modal.App("fitdit-image-check", image=image)


@app.function()
def check() -> dict:
    """Verify gradio + FitDiT repo are present."""
    import os
    import subprocess
    import sys

    sys.path.insert(0, "/opt/fitdit")

    out = {}
    out["python_version"] = sys.version
    try:
        import gradio  # type: ignore[import-not-found]

        out["gradio_version"] = getattr(gradio, "__version__", "unknown")
    except Exception as exc:
        out["gradio_error"] = str(exc)

    out["fitdit_root"] = sorted(os.listdir("/opt/fitdit"))[:20] if os.path.exists("/opt/fitdit") else "missing"
    out["pip_list_top"] = subprocess.run(
        ["pip", "list", "--format=columns"], capture_output=True, text=True, check=False
    ).stdout.splitlines()[:30]
    return out


@app.local_entrypoint()
def main() -> None:
    result = check.remote()
    for k, v in result.items():
        print(f"\n--- {k} ---")
        if isinstance(v, list):
            for line in v:
                print(line)
        else:
            print(v)
