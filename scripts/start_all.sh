#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ ! -f ".venv/Scripts/activate" ]; then
    echo "[ERROR] Virtual environment not found. Run: python -m venv .venv"
    exit 1
fi

source .venv/Scripts/activate

echo "========================================"
echo "  JNAO - Start All Services"
echo "========================================"
echo "[START] $(date '+%H:%M:%S')"
echo ""

# Clean port 8012
echo "[INFO] Cleaning port 8012..."
PID=$(lsof -ti :8012 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "  [KILL] PID $PID on port 8012"
    kill -9 $PID 2>/dev/null || true
    sleep 1
fi

# Backend (background)
echo "[TIME] backend start: $(date '+%H:%M:%S')"
echo "[INFO] Starting backend on http://127.0.0.1:8012"
mkdir -p logs
cd backend && uvicorn main:app --host 127.0.0.1 --port 8012 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Frontend (foreground)
echo "[TIME] frontend start: $(date '+%H:%M:%S')"
echo "[INFO] Starting frontend on http://127.0.0.1:5185"
echo ""
echo "  Backend:  http://127.0.0.1:8012  (logs: logs/backend.log)"
echo "  Frontend: http://127.0.0.1:5185"
echo "  Ctrl+C to stop both"
echo "========================================"
echo ""

cleanup() {
    echo ""
    echo "[INFO] Stopping backend (PID $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || true
    echo "[INFO] All services stopped."
}
trap cleanup EXIT INT TERM

cd h5_fronted
if [ ! -d "node_modules" ]; then
    echo "[INFO] Installing frontend dependencies..."
    npm install
fi

npm run dev
