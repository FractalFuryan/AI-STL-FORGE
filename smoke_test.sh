#!/usr/bin/env bash

set -euo pipefail

echo "Running STL Forge smoke test..."

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_http() {
  local label="$1"
  local url="$2"
  echo -n "Checking ${label}... "
  if curl -fsS "$url" >/dev/null; then
    echo -e "${GREEN}ok${NC}"
  else
    echo -e "${RED}failed${NC}"
    return 1
  fi
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo ""
  fi
}

COMPOSE="$(compose_cmd)"
if [[ -z "$COMPOSE" ]]; then
  echo "Docker Compose is not available."
  exit 1
fi

echo -e "\n${YELLOW}1/8 Starting stack${NC}"
$COMPOSE up -d

echo -e "\n${YELLOW}2/8 Waiting for services${NC}"
sleep 15

echo -e "\n${YELLOW}3/8 Health checks${NC}"
check_http "backend live" "http://localhost:8000/api/health/live"
check_http "backend ready" "http://localhost:8000/api/health/ready"
check_http "frontend" "http://localhost:5173"

if docker exec "$($COMPOSE ps -q redis)" redis-cli ping 2>/dev/null | grep -q PONG; then
  echo -e "Checking redis... ${GREEN}ok${NC}"
else
  echo -e "Checking redis... ${YELLOW}skipped${NC}"
fi

echo -e "\n${YELLOW}4/8 API checks${NC}"
HEALTH_JSON="$(curl -fsS http://localhost:8000/api/health)"
VERSION_JSON="$(curl -fsS http://localhost:8000/api/version)"
if [[ "$HEALTH_JSON" == *"healthy"* ]]; then
  echo -e "Health payload... ${GREEN}ok${NC}"
else
  echo -e "Health payload... ${RED}failed${NC}"
  exit 1
fi
if [[ "$VERSION_JSON" == *"version"* ]]; then
  echo -e "Version payload... ${GREEN}ok${NC}"
else
  echo -e "Version payload... ${RED}failed${NC}"
  exit 1
fi

RATE_MODE="$(curl -sSI http://localhost:8000/api/health/live | tr -d '\r' | grep -i '^X-RateLimit-Mode:' || true)"
if [[ -n "$RATE_MODE" ]]; then
  echo "Rate limiter header: $RATE_MODE"
else
  echo -e "Rate limiter header: ${YELLOW}not present${NC}"
fi

echo -e "\n${YELLOW}5/8 Generate test STL${NC}"
python3 - <<'PY'
import struct
import zlib

w = 100
h = 100
raw = bytearray()
for y in range(h):
  raw.append(0)
  for x in range(w):
    raw.append((x + y) % 256)

def chunk(tag: bytes, data: bytes) -> bytes:
  return (
    struct.pack("!I", len(data))
    + tag
    + data
    + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
  )

sig = b"\x89PNG\r\n\x1a\n"
ihdr = struct.pack("!IIBBBBB", w, h, 8, 0, 0, 0, 0)
idat = zlib.compress(bytes(raw), level=9)
png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
with open("test_input.png", "wb") as f:
  f.write(png)
PY

HTTP_CODE="$(curl -sS -w '%{http_code}' -o test_output.stl \
  -F image=@test_input.png \
  -F 'params={"mode":"heightmap","gamma":1.2}' \
  http://localhost:8000/api/generate-stl)"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo -e "STL generation... ${RED}failed (${HTTP_CODE})${NC}"
  exit 1
fi

STL_SIZE="$(wc -c < test_output.stl)"
if [[ "$STL_SIZE" -gt 84 ]]; then
  echo -e "STL generation... ${GREEN}ok${NC} (${STL_SIZE} bytes)"
else
  echo -e "STL generation... ${RED}failed (too small)${NC}"
  exit 1
fi

echo -e "\n${YELLOW}6/8 Batch generation${NC}"
BATCH_CODE="$(curl -sS -w '%{http_code}' -o test_batch.zip \
  -F images=@test_input.png \
  -F images=@test_input.png \
  -F 'params={"mode":"heightmap"}' \
  http://localhost:8000/api/generate-batch)"
if [[ "$BATCH_CODE" != "200" ]]; then
  echo -e "Batch endpoint... ${RED}failed (${BATCH_CODE})${NC}"
  exit 1
fi

if [[ -s test_batch.zip ]] && unzip -l test_batch.zip | grep -q '.stl'; then
  echo -e "Batch endpoint... ${GREEN}ok${NC}"
else
  echo -e "Batch endpoint... ${RED}failed${NC}"
  exit 1
fi

echo -e "\n${YELLOW}7/8 Metrics and logs${NC}"
if curl -fsS http://localhost:8000/api/metrics >/dev/null; then
  echo -e "Metrics endpoint... ${GREEN}ok${NC}"
else
  echo -e "Metrics endpoint... ${YELLOW}skipped${NC}"
fi

ERROR_LINES="$($COMPOSE logs --tail=80 backend 2>/dev/null | awk 'BEGIN { c = 0 } /[Ee]rror|[Ee]xception/ && $0 !~ /rate_limit_fail/ { c++ } END { print c }')"
if [[ "$ERROR_LINES" == "0" ]]; then
  echo -e "Backend recent logs... ${GREEN}clean${NC}"
else
  echo -e "Backend recent logs... ${YELLOW}${ERROR_LINES} potential error lines${NC}"
fi

echo -e "\n${YELLOW}8/8 Resource snapshot${NC}"
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' || true

rm -f test_input.png test_output.stl test_batch.zip

echo -e "\n${GREEN}Smoke test complete${NC}"
