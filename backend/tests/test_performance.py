import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.benchmark
def test_generation_performance(test_image_bytes):
    start = time.time()
    response = client.post(
        "/api/generate-stl",
        files={"image": ("test.png", test_image_bytes, "image/png")},
        data={"params": json.dumps({"mode": "heightmap"})},
    )
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 10
