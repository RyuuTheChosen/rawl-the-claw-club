# Rawl Platform

## Project Structure
Monorepo with 4 packages:
- `packages/backend/` — Python (FastAPI + Celery) backend
- `packages/frontend/` — Next.js 14 (App Router) frontend
- `packages/contracts/` — Solana Anchor smart contracts
- `packages/shared/` — Shared TypeScript types

## Key Commands
- Backend: `cd packages/backend && uvicorn rawl.main:create_app --factory --reload`
- Frontend: `cd packages/frontend && npm run dev`
- Contracts: `cd packages/contracts && anchor build && anchor test`
- Tests: `cd packages/backend && pytest`
- Lint: `cd packages/backend && ruff check src/`
- DB migrations: `cd packages/backend && alembic upgrade head`
- Docker services: `docker compose up -d` (PostgreSQL, Redis, MinIO)

## Architecture
- SDD: `Rawl_SDD.md` is the authoritative spec
- Game adapters in `packages/backend/src/rawl/game_adapters/` — one per fighting game
- Match engine in `packages/backend/src/rawl/engine/` — DIAMBRA-based game loop
- WebSocket streaming: video (binary JPEG 30fps) + data (JSON 10Hz)
- Solana smart contracts handle betting pools, payouts, and match resolution
- All match results are hashed and uploaded to S3 before on-chain resolution

## Conventions
- Python: Ruff for linting, asyncio throughout, Pydantic for validation
- TypeScript: ESLint + Prettier, strict mode
- Rust: Standard Anchor conventions
- All API responses use cursor-based pagination
- Structured JSON logging with trace IDs
