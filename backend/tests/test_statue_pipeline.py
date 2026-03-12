import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _image_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(120, 160, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_statue_job_creation():
    response = client.post(
        "/api/statue/generate",
        files={"image": ("subject.png", _image_bytes(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "job_id" in payload
    assert payload["status"] == "processing"


def test_statue_accepts_base_type():
    response = client.post(
        "/api/statue/generate",
        files={"image": ("subject.png", _image_bytes(), "image/png")},
        data={"base_type": "miniature"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processing"


def test_statue_rejects_invalid_base_type():
    response = client.post(
        "/api/statue/generate",
        files={"image": ("subject.png", _image_bytes(), "image/png")},
        data={"base_type": "invalid"},
    )

    assert response.status_code == 400
