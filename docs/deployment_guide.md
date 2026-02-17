# Rawl Platform — Deployment Guide

**Last updated:** 2026-02-18

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop
- Rust toolchain + Solana CLI + Anchor CLI
- PostgreSQL 16
- Redis 7

---

## Local Development

### 1. Start Infrastructure Services

```bash
docker compose up -d
```

This starts PostgreSQL (port 5432), Redis (port 6379), and MinIO (port 9000).

### 2. Backend Setup

```bash
cd packages/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn rawl.main:create_app --factory --reload --host 0.0.0.0 --port 8080
```

### 3. Start Celery Workers

In separate terminals:

```bash
# Worker (handles match execution, training, validation)
cd packages/backend
celery -A rawl.celery_app worker --loglevel=info --concurrency=4

# Beat scheduler (periodic tasks: matchmaking, health checks, retries)
cd packages/backend
celery -A rawl.celery_app beat --loglevel=info
```

### 4. Frontend Setup

```bash
cd packages/frontend

npm install
npm run dev
```

The frontend runs at `http://localhost:3000`.

### 5. Solana Local Validator (Optional)

For testing on-chain interactions:

```bash
solana-test-validator

# Deploy contracts
cd packages/contracts
anchor build
anchor deploy --provider.cluster localnet
```

---

## Environment Variables

### Backend (`packages/backend/.env`)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://rawl:rawl@localhost:5432/rawl

# Redis
REDIS_URL=redis://localhost:6379/0

# S3 / MinIO
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=rawl
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin

# Solana
SOLANA_RPC_URL=http://localhost:8899
PROGRAM_ID=<your_program_id>
ORACLE_KEYPAIR_PATH=/path/to/oracle-keypair.json

# Emulation (stable-retro — runs in WSL2 only)
RETRO_GAME=StreetFighterIISpecialChampionEdition-Genesis-v0
RETRO_OBS_SIZE=256

# App
SECRET_KEY=your-secret-key-for-jwt
LOG_LEVEL=INFO
```

### Frontend (`packages/frontend/.env.local`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8080/api
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080/gateway
NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws
NEXT_PUBLIC_SOLANA_NETWORK=devnet
NEXT_PUBLIC_SOLANA_RPC_URL=http://localhost:8899
NEXT_PUBLIC_PROGRAM_ID=<your_program_id>
```

---

## Database Migrations

```bash
cd packages/backend

# Apply all migrations
alembic upgrade head

# Create a new migration (after model changes)
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1

# Show current migration status
alembic current
```

### Migration History

| Version | Description |
|---------|-------------|
| 001 | Initial schema (7 tables) |
| 002 | Add missing fields (claimed_at, division_tier, tier, gpu_type, queue_position) |

---

## Running Tests

### Backend

```bash
cd packages/backend

# All tests
pytest

# Specific test suite
pytest tests/test_solana/
pytest tests/test_game_adapters/

# With coverage
pytest --cov=rawl --cov-report=html
```

### Contracts

```bash
cd packages/contracts

# Build
anchor build

# Test (requires solana-test-validator)
anchor test
```

### Frontend

```bash
cd packages/frontend

# Lint
npm run lint

# Type check
npx tsc --noEmit
```

---

## Linting

```bash
# Backend
cd packages/backend
ruff check src/
ruff format src/

# Frontend
cd packages/frontend
npm run lint
npx prettier --write src/
```

---

## Docker Compose Services

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: rawl
      POSTGRES_PASSWORD: rawl
      POSTGRES_DB: rawl
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rawl"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  minio:
    image: minio/minio:latest
    ports: ["9000:9000", "9001:9001"]
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
```

---

## Production Deployment

### Current Stack: Railway + Vercel

The platform is deployed using Railway (backend) and Vercel (frontend):

| Component | Platform | Notes |
|-----------|----------|-------|
| Backend API | Railway | Auto-deploys from `main`, runs `alembic upgrade head` on start |
| Celery Worker | Railway | Separate service, same codebase |
| Celery Beat | Railway | Separate service, periodic task scheduler |
| PostgreSQL | Railway | Managed PostgreSQL add-on |
| Redis | Railway | Managed Redis add-on |
| Frontend | Vercel | Next.js, auto-deploys from `main` |
| Solana | Devnet | Program ID: `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` |

Configuration: `python scripts/railway_config.py <RAILWAY_TOKEN>`

See `docs/devnet_deployment.md` for step-by-step deployment instructions.

### Kubernetes (Alternative)

Deployment manifests are in `infra/k8s/` for self-hosted deployment:

| Manifest | Replicas | Notes |
|----------|----------|-------|
| `backend-deployment.yaml` | 2 | Readiness probe on `/api/health`, port 8080 |
| `worker-deployment.yaml` | 2 | CPU-only (no GPU needed for match execution) |
| `account-listener-deployment.yaml` | 1 | WebSocket to Solana RPC |

### Monitoring

- **Health:** `GET /api/health` — returns 8 component checks
- **Metrics:** `GET /api/metrics` — Prometheus exposition format
- **Logs:** structlog JSON output with trace IDs

### Celery Beat Tasks

| Task | Interval | Purpose |
|------|----------|---------|
| `check_match_heartbeats` | 30s | Detect stale matches (60s timeout) |
| `schedule_pending_matches` | 30s | Elo-proximity matchmaking |
| `retry_failed_uploads_task` | 5min | Retry failed S3 uploads |
| `seasonal_reset_task` | Quarterly (cron) | Reset Elo ratings (Jan/Apr/Jul/Oct 1st) |

---

## Troubleshooting

### Common Issues

**Database connection refused**
- Ensure PostgreSQL is running: `docker compose ps`
- Check `DATABASE_URL` in `.env`

**Redis connection error**
- Ensure Redis is running: `docker compose ps`
- Check `REDIS_URL` in `.env`

**Retro health check failing**
- stable-retro must be installed in **WSL2** (does not build on native Windows)
- Install: `wsl -d Ubuntu-22.04 -- pip3 install stable-retro`
- ROM: Copy `Street Fighter II' - Special Champion Edition (U) [!].bin` as `rom.md` to stable-retro data dir
- ROM path: `/usr/local/lib/python3.10/dist-packages/stable_retro/data/stable/StreetFighterIISpecialChampionEdition-Genesis-v0/rom.md`
- No BIOS files needed (Genesis does not require BIOS)

**Solana RPC health check failing**
- Start local validator: `solana-test-validator`
- Or update `SOLANA_RPC_URL` to a devnet/mainnet RPC

**Celery tasks not executing**
- Ensure a worker is running: `celery -A rawl.celery_app worker --loglevel=info`
- Check Redis is reachable (Celery uses it as broker)

**Match execution fails**
- Verify ROM is installed (in WSL2): `python3 -c "import stable_retro; stable_retro.data.get_romfile_path('StreetFighterIISpecialChampionEdition-Genesis-v0')"`
- Emulation must run in WSL2 — Celery workers need WSL2 environment
- Check model S3 keys exist in MinIO/S3
- Review Celery worker logs for stack traces
