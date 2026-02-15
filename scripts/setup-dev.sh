#!/usr/bin/env bash
set -euo pipefail

echo "=== Rawl Development Setup ==="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ is required but not installed."; exit 1; }

# Create .env from example if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

# Start Docker services
echo "Starting Docker services..."
docker compose up -d
echo "Waiting for services to be healthy..."
sleep 5

# Backend setup
echo "Setting up backend..."
cd packages/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo "Backend setup complete."
cd ../..

# Frontend setup
if command -v npm >/dev/null 2>&1; then
    echo "Setting up frontend..."
    cd packages/frontend
    npm install
    echo "Frontend setup complete."
    cd ../..
else
    echo "npm not found, skipping frontend setup."
fi

# Create MinIO bucket
echo "Creating S3 bucket in MinIO..."
python3 -c "
import asyncio
import sys
sys.path.insert(0, 'packages/backend/src')
from rawl.s3_client import ensure_bucket
asyncio.run(ensure_bucket())
print('S3 bucket ready.')
" 2>/dev/null || echo "MinIO bucket creation skipped (will be created on first use)"

echo ""
echo "=== Setup Complete ==="
echo "Start backend:  make dev-backend"
echo "Start frontend: make dev-frontend"
echo "Start worker:   make dev-worker"
echo "Run tests:      make test"
