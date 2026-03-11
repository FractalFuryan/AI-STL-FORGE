# AI STL Forge v2.0 - Production Release

## Overview
This release adds cookie-cutter generation, mesh generation performance improvements, and production observability.

## Highlights
- Cookie-cutter generation mode from images
- Vectorized mesh generation path for faster STL builds
- AI depth mode with lazy model loading
- Redis-capable distributed rate limiting
- Prometheus metrics and Grafana dashboards

## API Additions
- Batch generation endpoint (`/api/generate-batch`)
- Health endpoints (`/api/health/live`, `/api/health/ready`, `/api/health`)
- Version endpoint (`/api/version`)

## Validation
- Backend tests passing
- Frontend production build passing
- Smoke test passing with cookie-cutter coverage

## Upgrade Notes
- No breaking changes for existing heightmap/lithophane/emboss/relief clients.
- New mode identifier: `cookie-cutter`.
