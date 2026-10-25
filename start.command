#!/bin/bash
# ReForm3D demo: starts the design server (port 8000) and the website (port 5500), then opens the page.
# First run installs the Python packages (a few minutes, once). Close this window or press Ctrl+C to stop.
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ and run this again."; read -r -p "Press Enter to close"; exit 1; fi
cd "$ROOT/backend" || exit 1
if [ ! -x .venv/bin/uvicorn ]; then
  echo "First run: installing packages (only once)..."
  "$PY" -m venv .venv && ./.venv/bin/pip install --upgrade pip -q && ./.venv/bin/pip install -r requirements.txt || { echo "Install failed. Send the error above."; read -r -p "Press Enter to close"; exit 1; }
fi
set -a; source .env; set +a
lsof -ti tcp:8000 | xargs kill 2>/dev/null; lsof -ti tcp:5500 | xargs kill 2>/dev/null
./.venv/bin/uvicorn app.main:app --port 8000 &
BACK=$!
(cd "$ROOT/frontend/dist" && exec "$PY" -m http.server 5500 >/dev/null 2>&1) &
FRONT=$!
trap 'kill $BACK $FRONT 2>/dev/null' EXIT INT TERM
for i in $(seq 1 60); do curl -s http://localhost:8000/health >/dev/null && break; sleep 1; done
echo; echo "ReForm3D is running:  http://localhost:5500/reform3d.html?api=http://localhost:8000"; echo
open "http://localhost:5500/reform3d.html?api=http://localhost:8000"
wait
