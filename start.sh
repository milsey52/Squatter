#!/bin/bash
set -e

# Activate virtual environment
. /opt/venv/bin/activate

echo "Running database migrations..."
alembic upgrade head

echo "Seeding static data..."
python scripts/seed_static_data.py

echo "Starting server..."
uvicorn main:app --host 0.0.0.0 --port $PORT
