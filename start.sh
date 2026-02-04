#!/bin/bash
set -e

# Activate virtual environment
. /opt/venv/bin/activate

echo "Skipping migrations (alembic temporarily hidden)..."

echo "Starting server..."
uvicorn main:app --host 0.0.0.0 --port $PORT
