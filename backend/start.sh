#!/bin/bash
set -e

echo "=== SPT Hospital HRMS — Production Startup ==="

# Run database initialization (creates tables + seeds)
echo "Initializing database..."
python -m scripts.init_db

# Start the application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
