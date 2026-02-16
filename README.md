# Rawl `[Alpha]`

**AI fighting game arena with on-chain betting.**

Train AI agents on your own hardware. Upload them to fight in ranked matches on classic arcade titles. Bet SOL on the outcome.

> Most AI competition platforms own the training loop. Rawl doesn't — you train on your GPUs, we run the fights. Every match is emulated server-side, streamed live, hashed for integrity, and settled on Solana.

---

## How It Works

```
 Train                    Fight                     Bet
 ─────                    ─────                     ───
 Users train agents       Platform runs matches     Spectators wager SOL
 on their own GPUs        via stable-retro          through on-chain pools
       │                        │                         │
       ▼                        ▼                         ▼
 Upload checkpoint ──► Matchmaker pairs by Elo ──► Solana smart contract
                              │                     escrows & pays out
                              ▼
                     Live stream via WebSocket
                     (video @ 30fps + data @ 10Hz)
```

### Training Your Agent

Training happens off-platform. You bring your own GPUs and training setup.

1. **Pick a game** — SF2 Champion Edition (Genesis) is the launch title
2. **Train locally** — Use stable-retro + Stable-Baselines3 (PPO) against built-in AI or self-play
3. **Upload checkpoint** — Submit your `.zip` model via the agent gateway API
4. **Calibration** — The platform runs 5 matches against reference bots to seed your Elo
5. **Ranked play** — Your agent enters the matchmaking queue and fights at its skill level

### Betting Flow

```
 Place Bet ──► Match Runs ──► Result Hashed ──► On-Chain Resolve ──► Auto-Payout
    │                                                                     │
    ▼                                                                     ▼
 SOL goes to          Oracle submits winner                    Winners withdraw
 escrow vault         to smart contract                        from vault PDA
```

Betting pools are Solana PDAs managed by the Rawl program. SOL is escrowed in a program-owned vault on bet placement. When the match resolves, the oracle signs the result on-chain and winners can claim proportional payouts. If a match is cancelled, all bets are refunded.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14)                                           │
│  App Router + Zustand + Tailwind + Solana Wallet Adapter         │
├──────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)              │  Workers (Celery)               │
│  REST API + Agent Gateway       │  Match Engine + Scheduler       │
│  WebSocket Streaming            │  Elo Calibration + Seasonal     │
├─────────────────────────────────┼────────────────────────────────┤
│  Emulation (stable-retro)       │  Solana Program (Anchor)        │
│  In-process RetroEngine         │  MatchPool, Bet, PlatformConfig │
│  Genesis / SF2 Champion Ed.     │  Escrow, Payout, Refund         │
├──────────────────────────────────────────────────────────────────┤
│  PostgreSQL    Redis    MinIO (S3)    Solana Validator            │
└──────────────────────────────────────────────────────────────────┘
```

## Features

- **Own-GPU Training** — No vendor lock-in on compute. Train anywhere, fight here.
- **Elo Ranking** — Calibration pipeline, configurable K-factors, quarterly seasonal resets
- **Live Streaming** — Binary JPEG video and structured JSON data over WebSocket
- **On-Chain Betting** — Solana escrow pools with automated payout on match resolution
- **Matchmaking** — Elo-based queue with sliding windows and priority scheduling
- **Replay Integrity** — Every match hashed, recorded, and archived to S3
- **Multi-Game** — Pluggable adapter system for different fighting games

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Zustand, Solana wallet-adapter |
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async), Celery, Redis |
| Emulation | stable-retro (Genesis core), OpenCV for frame processing |
| Blockchain | Solana, Anchor 0.30, solana-py, solders |
| Infrastructure | PostgreSQL, Redis, MinIO (S3-compatible), Docker Compose |

## Project Structure

```
packages/
  backend/        Python backend — API, match engine, services, Solana integration
  frontend/       Next.js 14 — arena viewer, betting UI, wallet connection
  contracts/      Solana Anchor program — betting pools, payouts, platform config
  shared/         Shared TypeScript types and constants
scripts/          Dev utilities and testing scripts
infra/            Docker and Kubernetes configs
```

## Quick Start

### Prerequisites

- Python >= 3.11, Node >= 20
- Docker (for PostgreSQL, Redis, MinIO)
- Solana CLI + test validator (WSL2 on Windows)

### Setup

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Run database migrations
cd packages/backend && alembic upgrade head

# 3. Start backend (port 8080)
make dev-backend

# 4. Start Celery worker + beat (separate terminals)
make dev-worker
make dev-beat

# 5. Start frontend (port 3000)
make dev-frontend
```

### Solana (local devnet)

```bash
# In WSL2:
solana-test-validator

# Initialize platform config (needs funded oracle wallet)
python scripts/init-platform.py
```

### Seed test data

```bash
python scripts/seed-db.py
```

## Development

```bash
make test            # Run all backend tests
make test-adapters   # Game adapter tests only
make test-engine     # Engine tests only
make lint            # Ruff lint
make fmt             # Ruff format
```

See `make help` for all available commands.
