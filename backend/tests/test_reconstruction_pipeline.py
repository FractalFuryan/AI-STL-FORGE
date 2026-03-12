import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.ai.reconstructor import resolve_model
from app.main import app
from app.routes.reconstruct import job_status

client = TestClient(app)


def create_test_image(width: int = 96, height: int = 96, fmt: str = "PNG") -> bytes:
    img = Image.fromarray(np.random.randint(0, 255, (height, width, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.getvalue()


def make_image_file(filename: str = "test.png", fmt: str = "PNG") -> tuple[str, bytes, str]:
    return (filename, create_test_image(fmt=fmt), f"image/{fmt.lower()}")


@pytest.fixture(autouse=True)
def clear_reconstruct_jobs():
    job_status.clear()
    yield
    job_status.clear()


def test_reconstruct_rejects_non_image_upload():
    response = client.post(
        "/api/reconstruct/3d",
        files={"image": ("test.txt", b"not-image", "text/plain")},
    )
    assert response.status_code == 400
    assert "image" in response.json()["detail"].lower()


def test_reconstruct_rejects_empty_upload():
    response = client.post(
        "/api/reconstruct/3d",
        files={"image": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_reconstruct_rejects_invalid_preset(cookie_image_bytes):
    response = client.post(
        "/api/reconstruct/3d",
        files={"image": ("subject.png", cookie_image_bytes, "image/png")},
        data={"preset": "ultra"},
    )
    assert response.status_code == 400
    assert "preset" in response.json()["detail"].lower()


def test_reconstruct_rejects_invalid_decimate_ratio(cookie_image_bytes):
    response = client.post(
        "/api/reconstruct/3d",
        files={"image": ("subject.png", cookie_image_bytes, "image/png")},
        data={"decimate_ratio": "1.2"},
    )
    assert response.status_code == 400
    assert "decimate_ratio" in response.json()["detail"]


def test_resolve_model_mapping_contract():
    assert resolve_model("auto", "fast") == "triposr"
    assert resolve_model("auto", "balanced") == "sf3d"
    assert resolve_model("auto", "high") == "sf3d"
    assert resolve_model("sf3d", "fast") == "sf3d"
    assert resolve_model("triposr", "high") == "triposr"


def test_reconstruct_job_lifecycle_contract(cookie_image_bytes):
    start = client.post(
        "/api/reconstruct/3d",
        files={"image": ("subject.png", cookie_image_bytes, "image/png")},
        data={
            "model": "auto",
            "preset": "balanced",
            "target_height_mm": "120",
            "output_format": "stl",
            "repair": "true",
            "decimate_ratio": "0.8",
        },
    )
    assert start.status_code == 200
    payload = start.json()
    assert "job_id" in payload

    status = client.get(f"/api/reconstruct/3d/status/{payload['job_id']}")
    assert status.status_code == 200
    status_payload = status.json()
    assert "status" in status_payload
    assert "progress" in status_payload


def test_status_not_found_returns_404():
    response = client.get("/api/reconstruct/3d/status/missing-job")
    assert response.status_code == 404


def test_preview_download_contract(tmp_path: Path):
    job_id = "preview-download-job"
    glb = tmp_path / "preview.glb"
    stl = tmp_path / "mesh.stl"
    glb.write_bytes(b"fake-glb")
    stl.write_bytes(b"fake-stl")

    job_status[job_id] = {
        "status": "completed",
        "progress": 100,
        "output_path": str(stl),
        "filename": f"reconstruct_{job_id}.stl",
        "preview_path": str(glb),
        "preview_filename": f"reconstruct_{job_id}.glb",
    }

    preview = client.get(f"/api/reconstruct/3d/preview/{job_id}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "model/gltf-binary"
    assert preview.content == b"fake-glb"

    download = client.get(f"/api/reconstruct/3d/download/{job_id}")
    assert download.status_code == 200
    assert download.content == b"fake-stl"
