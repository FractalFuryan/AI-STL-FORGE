from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PIL import Image


def remove_background(image_path: str) -> str:
    """
    Optional background removal stage.
    Falls back to passthrough copy if rembg is unavailable.
    """
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    try:
        from rembg import remove  # type: ignore

        with Image.open(src).convert("RGBA") as img:
            out = remove(img)
            fd, out_path = tempfile.mkstemp(suffix=".png", prefix="subject_")
            Path(out_path).unlink(missing_ok=True)
            out.save(out_path)
            return out_path
    except Exception:
        fd, out_path = tempfile.mkstemp(suffix=src.suffix or ".png", prefix="subject_")
        Path(out_path).unlink(missing_ok=True)
        shutil.copy2(src, out_path)
        return out_path
