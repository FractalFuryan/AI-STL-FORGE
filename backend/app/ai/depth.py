from __future__ import annotations

import logging
import os
import tempfile

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_device = None
_processor = None
_model = None


def _load_depth_model() -> bool:
    """Try to lazily load Depth Anything v2; return False if unavailable."""
    global _device, _processor, _model
    if _model is not None:
        return True

    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model_name = os.getenv("DEPTH_MODEL_NAME", "depth-anything/Depth-Anything-V2-Small-hf")
        _processor = AutoImageProcessor.from_pretrained(model_name)
        _model = AutoModelForDepthEstimation.from_pretrained(model_name).to(_device)
        _model.eval()
        logger.info("Depth model loaded: %s", model_name)
        return True
    except Exception as exc:
        logger.warning("Depth model unavailable, using luminance fallback: %s", exc)
        _processor = None
        _model = None
        _device = None
        return False


async def estimate_depth(image_path: str) -> str:
    """
    Generate a depth map and return .npy path.
    If AI deps are unavailable, uses normalized luminance inversion fallback.
    """
    loaded = _load_depth_model()

    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    if loaded:
        import torch

        inputs = _processor(images=image, return_tensors="pt").to(_device)
        with torch.no_grad():
            outputs = _model(**inputs)
            depth = outputs.predicted_depth

        depth = torch.nn.functional.interpolate(
            depth.unsqueeze(1),
            size=(height, width),
            mode="bicubic",
            align_corners=False,
        ).squeeze().cpu().numpy()

        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-6)
    else:
        arr = np.asarray(image.convert("L"), dtype=np.float32)
        arr = 255.0 - arr
        depth = (arr - arr.min()) / (arr.max() - arr.min() + 1e-6)

    fd, out_path = tempfile.mkstemp(suffix=".npy", prefix="depth_")
    os.close(fd)
    np.save(out_path, depth)
    return out_path
