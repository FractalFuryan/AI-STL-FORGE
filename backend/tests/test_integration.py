import concurrent.futures
import io
import json
import sys
from pathlib import Path

import pytest
import trimesh
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.routes.generate import get_cache
from app.services.depth_estimator import depth_estimator

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    cache = get_cache()
    cache.clear()
    yield


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "ai" in data
    assert "cache" in data
    assert "system" in data


def test_generate_stl_heightmap(test_image_bytes):
    params = {
        "mode": "heightmap",
        "gamma": 1.2,
        "smooth_sigma": 0.5,
        "base_thickness": 2.0,
        "max_height": 10.0,
    }

    response = client.post(
        "/api/generate-stl",
        files={"image": ("test.png", test_image_bytes, "image/png")},
        data={"params": json.dumps(params)},
    )

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"

    mesh = trimesh.load(io.BytesIO(response.content), file_type="stl")
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0


def test_generate_stl_cookie_cutter(cookie_image_bytes):
    params = {
        "mode": "cookie-cutter",
        "cutter_height": 10.0,
        "cutter_thickness": 2.0,
        "target_width_mm": 90.0,
    }

    response = client.post(
        "/api/generate-stl",
        files={"image": ("cookie.png", cookie_image_bytes, "image/png")},
        data={"params": json.dumps(params)},
    )

    assert response.status_code == 200
    mesh = trimesh.load(io.BytesIO(response.content), file_type="stl")
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0
    bounds = mesh.bounds
    height = float(bounds[1][2] - bounds[0][2])
    assert height == pytest.approx(10.0, rel=0.2)


def test_generate_stl_cookie_cutter_no_shape(blank_image_bytes):
    with pytest.raises(ValueError, match="No shape detected"):
        client.post(
            "/api/generate-stl",
            files={"image": ("blank.png", blank_image_bytes, "image/png")},
            data={"params": json.dumps({"mode": "cookie-cutter"})},
        )


def test_cache_hit_behavior(test_image_bytes):
    params = {"mode": "heightmap"}

    first = client.post(
        "/api/generate-stl",
        files={"image": ("test.png", test_image_bytes, "image/png")},
        data={"params": json.dumps(params)},
    )
    second = client.post(
        "/api/generate-stl",
        files={"image": ("test.png", test_image_bytes, "image/png")},
        data={"params": json.dumps(params)},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert first.content == second.content


def test_rate_limit_headers(test_image_bytes):
    params = {"mode": "heightmap"}
    response = client.post(
        "/api/generate-stl",
        files={"image": ("test.png", test_image_bytes, "image/png")},
        data={"params": json.dumps(params)},
    )

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


def test_invalid_image_type():
    response = client.post(
        "/api/generate-stl",
        files={"image": ("test.txt", b"not-image", "text/plain")},
        data={"params": json.dumps({"mode": "heightmap"})},
    )
    assert response.status_code == 400


def test_large_image_rejection(large_image_bytes):
    response = client.post(
        "/api/generate-stl",
        files={"image": ("large.png", large_image_bytes, "image/png")},
        data={"params": json.dumps({"mode": "heightmap"})},
    )
    assert response.status_code == 413


def test_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cache_size_mb" in data
    assert "cache_entries" in data


def test_batch_cookie_cutter(cookie_image_bytes):
    params = {
        "mode": "cookie-cutter",
        "cutter_height": 9.0,
        "cutter_thickness": 2.0,
    }
    response = client.post(
        "/api/generate-batch",
        files=[
            ("images", ("cookie1.png", cookie_image_bytes, "image/png")),
            ("images", ("cookie2.png", cookie_image_bytes, "image/png")),
        ],
        data={"params": json.dumps(params)},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_warmup_endpoint():
    response = client.post("/api/health/warmup")
    if depth_estimator.check_available():
        assert response.status_code == 200
    else:
        assert response.status_code == 400


@pytest.mark.concurrent
def test_concurrent_requests(test_image_bytes):
    def make_request():
        return client.post(
            "/api/generate-stl",
            files={"image": ("test.png", test_image_bytes, "image/png")},
            data={"params": json.dumps({"mode": "heightmap"})},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(make_request) for _ in range(4)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
