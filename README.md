# AI-STL-FORGE

AI STL Forge converts images into 3D printable STL files using a production-ready FastAPI backend and a real-time React + Three.js frontend.

[![Python](https://img.shields.io/badge/python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?style=for-the-badge&logo=docker)](https://docker.com)
[![Redis](https://img.shields.io/badge/redis-rate_limiter-DC382D?style=for-the-badge&logo=redis)](https://redis.io)

## Features

### Generation Modes

| Mode | Description | Best For |
|------|-------------|----------|
| `heightmap` | Grayscale to depth mapping | Terrain, relief maps |
| `lithophane` | Inverted depth for backlit prints | Portraits, photos |
| `emboss` | Edge-boosted details | Logos, symbols |
| `relief` | Baseline + detail blend | Decorative plaques |
| `ai-depth` | Optional neural depth estimation | Real depth from flat photos |
| `cookie-cutter` | Outline-based cutter mesh | Cookie cutters and stamps |

### Mesh Pipeline

- Vectorized heightmap mesh generation for faster builds on high resolutions.
- Manifold mesh output with top, base, and side walls.
- Optional adaptive remesh for reduced STL size.
- STL output aligned so model base sits on `Z=0`.

### Platform and Ops

- FastAPI async API with request guardrails and rate limiting.
- Redis-backed distributed limiter mode (`USE_REDIS_RATE_LIMIT=true`).
- Hash-based cache with TTL + background cleanup.
- Prometheus metrics endpoint and Grafana dashboards.
- Health probes (`live`, `ready`, `health`, `ai`) and warmup endpoint.

## Quick Start

### Docker Compose

```bash
git clone https://github.com/FractalFuryan/AI-STL-FORGE
cd AI-STL-FORGE
docker compose up -d --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

### Local Dev

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Architecture

```text
Browser (React + Three.js)
	|
	v
FastAPI API (/api/*)
	|
	+--> STL Generator (NumPy/SciPy/trimesh)
	+--> Optional AI Depth Estimator
	+--> File Cache (TTL/LRU cleanup)
	+--> Rate Limiter (memory or Redis)
	|
	+--> /api/metrics -> Prometheus -> Grafana
```

## API

### `POST /api/generate-stl`

`multipart/form-data`:

- `image`: image file
- `params`: JSON payload (example below)

```json
{
  "mode": "heightmap",
  "max_height": 8,
  "base_thickness": 2,
  "gamma": 1,
  "smooth_sigma": 0.5,
  "resolution": 192,
  "target_width_mm": 100,
  "adaptive_remesh": false
}
```

Response: binary STL download (`model/stl`).

Headers include:

- `X-Cache`: `HIT` or `MISS`
- `X-Process-Time`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Mode`
- `X-Request-ID`

### Other Important Endpoints

- `POST /api/generate-batch`
- `GET /api/stats`
- `GET /api/version`
- `GET /api/metrics`
- `GET /api/health`
- `GET /api/health/live`
- `GET /api/health/ready`
- `GET /api/health/ai`
- `POST /api/health/warmup`

## Performance Notes

- The vectorized mesh path reduces per-request Python loop overhead in the core geometry stage.
- Cache keys include generation parameters and API versioning for safer reuse.
- WebWorker preview keeps UI responsive during fast slider changes.

## Validation

Backend tests:

```bash
cd backend
pytest -q
```

Frontend build:

```bash
cd frontend
npm run build
```

Full stack smoke test:

```bash
./smoke_test.sh
```

## Deployment Helpers

- `build.sh`: build images with git/build metadata.
- `deploy.sh`: production-oriented compose deployment.
- `smoke_test.sh`: end-to-end health/API/STL/metrics validation.

## License

MIT
