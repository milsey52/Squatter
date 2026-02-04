#!/bin/bash
set -e

# Activate virtual environment
. /opt/venv/bin/activate

echo "Running database migrations..."
alembic -c alembic.ini.bak upgrade head

echo "Starting server..."
uvicorn main:app --host 0.0.0.0 --port $PORT
