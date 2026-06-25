#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "========================================"
echo "  JNAO Backend - FastAPI Server"
echo "========================================"
echo "[START] $(date '+%H:%M:%S')"
echo ""

if [ ! -f "backend/venv/bin/activate" ]; then
    echo "[ERROR] Virtual environment not found. Run: python -m venv backend/venv"
    exit 1
fi

echo "[TIME] venv activate start: $(date '+%H:%M:%S')"
source backend/venv/bin/activate
echo "[TIME] venv activate done:  $(date '+%H:%M:%S')"

# Clean port 8012
echo "[INFO] Cleaning port 8012..."
PID=$(lsof -ti :8012 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "  [KILL] PID $PID on port 8012"
    kill -9 $PID 2>/dev/null || true
    sleep 1
    echo "  [OK] Port 8012 cleared"
else
    echo "  [OK] Port 8012 is free"
fi

cd backend

echo "[TIME] uvicorn start: $(date '+%H:%M:%S')"
echo "[INFO] Starting backend on http://127.0.0.1:8012"
echo "[INFO] API docs: http://127.0.0.1:8012/docs"
echo ""

uvicorn main:app --host 127.0.0.1 --port 8012 --reload
