#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== NOVA Windows Build ==="

echo "[1/5] Installing backend dependencies..."
cd backend
pip install -r requirements.txt -q
cd ..

echo "[2/5] Running self-test..."
python tests/self_test.py

echo "[3/5] Running unit tests..."
cd backend
pytest ../tests/unit/ -v --tb=short
cd ..

echo "[4/5] Building frontend..."
cd frontend
npm install --silent
npm run build
npx vite build

echo "[5/5] Building Windows installer..."
npx electron-builder --win --x64 || {
  echo "WARNING: Windows build requires Windows or Wine."
  echo "Creating portable bundle instead..."
  mkdir -p release/portable
  cp -r frontend/dist release/portable/ui
  cp -r backend release/portable/backend
  cp frontend/electron/main.js release/portable/
  echo "Portable bundle created at release/portable/"
}

echo "=== Build complete ==="
ls -la release/ 2>/dev/null || true
