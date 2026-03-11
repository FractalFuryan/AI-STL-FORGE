# AI-STL-FORGE

AI STL Forge is a full-stack image-to-STL generator for 3D printing.

## Features

- Upload an image and convert it to printable STL.
- Four modes: `heightmap`, `lithophane`, `emboss`, and `relief`.
- AI mode: `ai-depth` (optional server-side depth estimation model).
- Manifold mesh output with top surface, base, and side walls.
- Live 3D preview in the browser using Three.js.
- Preview processing runs in a WebWorker to keep the UI responsive.
- Debounced preview jobs prevent worker overload during slider scrubbing.
- Hash-based backend cache with TTL and LRU-style cleanup for repeated image + parameter requests.
- API guardrails include request-size limits, image-dimension validation, and rate limiting.
- Printer presets for Ender 3 V3, Prusa MK4, and Bambu A1 Mini.
- Adjustable controls for resolution, gamma, max height, base thickness, and width.

## Stack

- Frontend: React + Vite + Three.js (`@react-three/fiber`)
- Backend: FastAPI + NumPy + Pillow + SciPy + trimesh
- Containerization: Docker + docker-compose

## Project Structure

```
AI-STL-FORGE/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── middleware.py
│   │   ├── models.py
│   │   ├── routes/
│   │   │   └── generate.py
│   │   └── services/
│   │       ├── cache.py
│   │       └── stl_generator.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/Preview3D.jsx
│   │   ├── hooks/useDebouncedWorker.js
│   │   └── workers/previewWorker.js
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml
```

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional: enable AI depth mode (large ML dependencies)
pip install -r requirements-ai.txt
# Optional: install test/dev tooling
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the app at `http://localhost:5173`.

## API

### `POST /api/generate-stl`

Multipart form fields:

- `image`: image file
- `params`: JSON string

Example params:

```json
{
	"mode": "heightmap",
	"max_height": 8,
	"base_thickness": 2,
	"gamma": 1,
	"smooth_sigma": 0,
	"resolution": 192,
	"target_width_mm": 100
}
```

Response: binary STL (`model/stl`) as downloadable attachment.

Additional response headers:

- `X-Cache`: `HIT` or `MISS`
- `X-Process-Time`: server-side request duration (seconds)
- `X-RateLimit-Limit`: allowed requests per minute
- `X-RateLimit-Remaining`: current remaining requests in window

### `GET /api/version`

Returns deployment metadata (`version`, `build_time`, `commit`, `branch`, `environment`).

### `GET /api/stats`

Returns cache stats:

- `cache_size_mb`
- `cache_entries`
- `max_cache_mb`
- `ttl_hours`

### Health and Warmup Endpoints

- `GET /api/health`: full service, cache, AI, system and rate-limiter status
- `GET /api/health/ai`: AI dependency and model-load status
- `POST /api/health/warmup`: start AI model preload in background
- `GET /api/health/live`: lightweight liveness probe
- `GET /api/health/ready`: readiness probe for deployments
- `GET /api/metrics`: Prometheus-formatted metrics
- `POST /api/generate-batch`: generate up to 10 STL files and download as zip
- `POST /api/admin/cache/clear`: clear cache (admin token required)
- `POST /api/admin/ai/unload`: unload AI model (admin token required)

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

## Build Metadata

Use [build.sh](build.sh) to inject git and build-time metadata into container builds:

```bash
./build.sh
```

## Redis Rate Limiting Toggle

Set `USE_REDIS_RATE_LIMIT=true` to enable distributed rate limiting via Redis. When disabled (default),
the app uses in-memory per-instance limiting.

Rate-limit responses include:

- `X-RateLimit-Mode`: `memory` or `redis`
- `X-Request-ID`: request trace ID

## Production Deployment

```bash
./deploy.sh
docker compose up -d --scale backend=3
```

## Docker

```bash
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
