#!/bin/sh
echo "[start.sh] PORT=${PORT} starting uvicorn on port ${PORT:-8011}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8011}"
