#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../h5_fronted"

if [ ! -d "node_modules" ]; then
    echo "[INFO] Installing dependencies..."
    npm install
fi

echo "========================================"
echo "  JNAO H5 Frontend - Vite Dev Server"
echo "========================================"
echo "[START] $(date '+%H:%M:%S')"
echo ""
echo "[TIME] vite start: $(date '+%H:%M:%S')"
echo "[INFO] Starting frontend on http://127.0.0.1:5185"
echo ""

npm run dev
