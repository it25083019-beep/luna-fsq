#!/bin/sh
set -e
# Render (and similar hosts) forward traffic to $PORT, default 10000.
# Local docker / the old Dockerfile used 8000.
port="${PORT:-8000}"
echo "[boot] uvicorn 0.0.0.0:${port}"
cd /app/my-project
exec uvicorn main:app --host 0.0.0.0 --port "$port"
