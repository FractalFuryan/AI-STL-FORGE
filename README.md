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

### Tabletop Toolkit (New)

- Parametric miniature generation (`human`, `creature`, `terrain`, `prop`)
- Modular dungeon kit ZIP generation
- Character customization endpoint (weapon/scale choices)
- Multi-view reconstruction endpoint (front/side/top images)

## Latest Update: Bust Generation System

### Bust Generation System

Bust generation is now fully integrated end-to-end across the AI-STL-FORGE platform.

The system uses a Signed Distance Field (SDF) procedural modeling engine to generate printable busts with customizable styles, proportions, and features.

This release introduces:

- Modular SDF bust generators
- Backend REST API endpoints
- Frontend bust generation UI
- Integration tests
- Docker smoke validation

Bust generation is now part of the core procedural asset pipeline alongside:

- Image to STL conversion
- Cookie cutter generation
- Heightmap and lithophane generation
- Procedural creatures and terrain (in development)

### Architecture Overview

Bust generation is built on a modular SDF engine that constructs geometry using mathematical primitives instead of polygon sculpting.

Key benefits:

- Guaranteed watertight meshes
- Smooth organic surfaces
- Fully procedural variation
- Highly customizable parameters
- Fast mesh generation

Bust geometry is composed from primitives such as:

- `sphere`
- `capsule`
- `cylinder`
- `cone`
- `box`
- `torus`

These primitives are combined using operations such as:

- `smooth_union`
- `subtract`
- `cut_plane`
- `transform`

The final mesh is extracted from sampled SDF fields and exported as STL.

### Bust Module Structure

```text
backend/app/generators/sdf/busts/
	base.py
	classical.py
	fantasy.py
	factory.py
	__init__.py
```

Core styles implemented:

- `classical`
- `fantasy`

Additional styles are exposed through the factory architecture and can be implemented incrementally:

- `sci_fi`
- `steampunk`
- `gothic`
- `cartoon`
- `anime`
- `realistic`
- `heroic`
- `villainous`
- `alien`
- `robot`

This modular design allows style generators to be added independently without changing the core pipeline.

### API Endpoints

Bust generation is available through the REST API.

Catalog endpoints:

- `GET /api/busts/styles`
- `GET /api/busts/races`
- `GET /api/busts/base-types`

Generation endpoints:

- `POST /api/busts/generate/{style}`
- `POST /api/busts/random/{style}`

Common parameters include:

- `style`
- `race`
- `base_type`
- `height`
- `resolution`
- `include_base`
- feature flags (`helmet`, `crown`, `beard`, and related toggles)

Responses return binary STL files ready for printing.

### Frontend Bust Generator

The frontend now includes a dedicated bust generator panel integrated into the main application.

Controls include:

- Style selector
- Race selector
- Bust base type
- Height control
- Mesh resolution and quality
- Optional display base
- Feature toggles (`helmet`, `crown`, `beard`, and related options)
- Random bust generation

Generated STL files download directly from the browser.

### Testing and Validation

Bust generation includes integration coverage and end-to-end validation.

Backend tests:

- 23 tests passing

Coverage includes:

- API catalog endpoints
- STL generation endpoints
- Random generation pipeline

Frontend:

- Production build successful

End-to-end validation:

- Docker smoke test passes with backend API, Redis, frontend, and mesh generation pipeline running successfully

### Current Capabilities

AI-STL-FORGE can now generate:

Procedural models:

- Character busts
- Fantasy characters
- Stylized portraits
- Procedural geometry

Image-based models:

- Lithophanes
- Heightmaps
- Cookie cutters
- Relief models

Export:

- Binary STL

Ready for:

- FDM printing
- Resin printing
- Tabletop miniatures
- Display busts

### Next Development Phase

Upcoming work includes dedicated generators for additional bust styles:

- `sci_fi`
- `steampunk`
- `gothic`
- `anime`
- `robot`
- `alien`

Each style will be implemented as an independent SDF module under:

```text
backend/app/generators/sdf/busts/
```

This keeps the architecture scalable while expanding the procedural asset library.

### Why SDF Modeling?

Traditional mesh modeling often leads to:

- non-manifold geometry
- broken meshes
- boolean failures

Signed Distance Fields solve this by defining shapes mathematically.

Benefits:

- perfectly closed surfaces
- smooth blending between shapes
- procedural variation
- fast mesh extraction

This makes SDFs ideal for procedural 3D printable assets.

### Project Direction

AI-STL-FORGE is evolving into a procedural 3D printing platform capable of generating:

- tabletop miniatures
- display busts
- creatures
- terrain
- custom STL assets

All powered by a scalable backend and procedural geometry engine.

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

### Tabletop Endpoints

- `POST /api/tabletop/parametric/generate`
- `POST /api/tabletop/modular/kit`
- `POST /api/tabletop/character/customize`
- `POST /api/tabletop/reconstruct`

### Action Figure Endpoints

- `POST /api/action-figure/extract-pose`
- `POST /api/action-figure/generate`
- `POST /api/action-figure/add-accessories`

### Creature Engine Endpoints

- `GET /api/creatures/species`
- `GET /api/creatures/presets/{species}`
- `POST /api/creatures/generate/{species}`
- `POST /api/creatures/mutate/{species}`
- `POST /api/creatures/hybrid`

### Bust Endpoints

- `GET /api/busts/styles`
- `GET /api/busts/races`
- `GET /api/busts/base-types`
- `POST /api/busts/generate/{style}`
- `POST /api/busts/random/{style}`

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
