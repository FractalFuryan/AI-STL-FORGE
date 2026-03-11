import io

import numpy as np
import pytest
from PIL import Image, ImageDraw


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


@pytest.fixture
def cookie_image_bytes() -> bytes:
    img = Image.new("L", (220, 220), color=255)
    draw = ImageDraw.Draw(img)
    draw.rectangle([45, 50, 175, 180], fill=0)
    draw.ellipse([30, 20, 90, 80], fill=0)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def blank_image_bytes() -> bytes:
    img = Image.new("L", (120, 120), color=255)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
