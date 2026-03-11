import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class DepthEstimator:
    """Lazy AI depth estimation wrapper.

    The heavy ML dependencies are loaded only when ai-depth mode is used.
    """

    def __init__(self, model_name: str = "depth-anything/Depth-Anything-V2-Small-hf") -> None:
        self.model_name = model_name
        self._processor: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None
        self._device: Any | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _ensure_dependencies(self) -> None:
        if self._torch is not None:
            return

        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        self._torch = torch
        self._AutoImageProcessor = AutoImageProcessor
        self._AutoModelForDepthEstimation = AutoModelForDepthEstimation
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def check_available(self) -> bool:
        try:
            import torch  # noqa: F401
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation  # noqa: F401

            return True
        except Exception:
            return False

    @property
    def model(self) -> Any | None:
        return self._model

    @property
    def device(self) -> Any | None:
        return self._device

    def _load_model_sync(self) -> None:
        self._ensure_dependencies()
        self._processor = self._AutoImageProcessor.from_pretrained(self.model_name)
        self._model = self._AutoModelForDepthEstimation.from_pretrained(self.model_name)
        self._model.to(self._device)
        self._model.eval()

    async def load_model(self) -> None:
        if self._model is not None:
            return

        if not self.check_available():
            raise RuntimeError("AI dependencies are not installed.")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._load_model_sync)
        logger.info("Depth model loaded: %s", self.model_name)

    def _estimate_depth_sync(self, image: Image.Image, target_size: tuple[int, int]) -> np.ndarray:
        assert self._processor is not None
        assert self._model is not None
        assert self._torch is not None

        import torch.nn.functional as F

        original_size = image.size
        resized = image.resize(target_size, Image.Resampling.LANCZOS)
        inputs = self._processor(images=resized, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with self._torch.no_grad():
            outputs = self._model(**inputs)
            depth = outputs.predicted_depth

        depth = F.interpolate(
            depth.unsqueeze(1),
            size=original_size[::-1],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        arr = depth.cpu().numpy().astype(np.float32)
        arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-6)
        return arr

    async def estimate_depth(self, image: Image.Image, target_size: tuple[int, int] = (384, 384)) -> np.ndarray:
        if self._model is None:
            await self.load_model()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._estimate_depth_sync, image, target_size)

    def cleanup(self) -> None:
        self._model = None
        self._processor = None


depth_estimator = DepthEstimator()
