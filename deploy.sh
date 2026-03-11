#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env.production ]]; then
  set -a
  source .env.production
  set +a
fi

export GIT_COMMIT="$(git rev-parse --short HEAD)"
export GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
export BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

docker compose build
docker compose pull
docker compose up -d

echo "Waiting for backend health..."
sleep 8
curl -fsS http://localhost:8000/api/health/live >/dev/null

echo "Deployment complete"
