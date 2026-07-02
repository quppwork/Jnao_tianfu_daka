#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "========================================"
echo "  JNAO - Build Docker Images"
echo "========================================"

docker compose build

echo ""
echo "[OK] Images built:"
docker images --format '  {{.Repository}}:{{.Tag}}' | grep jnao-daka || true
echo ""
echo "Start:  docker compose up -d"
echo "Stop:   docker compose down"
echo "Logs:   docker compose logs -f"
