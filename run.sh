#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"
ENV_FILE="$PROJECT_DIR/.env"

# ── Check .env exists ─────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found."
  echo "Run: cp .env.example .env  and add your API key."
  exit 1
fi

# ── Check venv exists ─────────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo "Virtual environment not found. Creating it..."
  python3 -m venv "$VENV"
  echo "Installing dependencies..."
  "$VENV/bin/pip" install -q --ignore-requires-python -r "$PROJECT_DIR/requirements.txt"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Last Mile — starting up"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Backend  →  http://localhost:8000"
echo "  API docs →  http://localhost:8000/docs"
echo "  Frontend →  http://localhost:8501"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  echo "Done."
}
trap cleanup INT TERM

# ── Start backend ─────────────────────────────────────────────────────────────
cd "$PROJECT_DIR"
"$VENV/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Give the backend a moment to bind before starting the frontend
sleep 2

# ── Start frontend ────────────────────────────────────────────────────────────
"$VENV/bin/streamlit" run "$PROJECT_DIR/frontend/app.py" \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false &
FRONTEND_PID=$!

# ── Wait for both ─────────────────────────────────────────────────────────────
wait "$BACKEND_PID" "$FRONTEND_PID"
