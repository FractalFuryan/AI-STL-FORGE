import io

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def test_image_bytes() -> bytes:
    arr = np.zeros((100, 100), dtype=np.uint8)
    for y in range(100):
        for x in range(100):
            arr[y, x] = (x + y) // 2

    img = Image.fromarray(arr, mode="L")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def large_image_bytes() -> bytes:
    rng = np.random.default_rng(seed=7)
    arr = rng.integers(0, 256, (10, 8300), dtype=np.uint8)
    img = Image.fromarray(arr, mode="L")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", compress_level=0)
    return buffer.getvalue()
