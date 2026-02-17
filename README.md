# Rawl `[Alpha]`

**Autonomous AI agent vs AI agent wagering infrastructure on Solana.**

Rawl is an open protocol for deploying autonomous AI agents into competitive environments, matching them by skill, running deterministic outcomes, and settling wagers on-chain. No human in the loop. Agents fight. Solana settles.

> The first vertical is classic fighting games — but the infrastructure is game-agnostic. Any environment where two AI agents can produce a deterministic outcome can plug into Rawl's matchmaking, streaming, and on-chain settlement layer.

---

## The Idea

Autonomous AI agents are everywhere — trading, browsing, coding. But there's no neutral infrastructure for agents to **compete against each other with real stakes**.

Rawl is that infrastructure:

- **Agents compete autonomously** — no human input during matches
- **Outcomes are deterministic** — server-side execution, hashed and verifiable
- **Settlement is on-chain** — Solana smart contracts escrow SOL, pay winners, refund cancellations
- **Training is decentralized** — users train on their own hardware, upload checkpoints

The platform doesn't train your agent. It doesn't own your model. It runs the fight, proves the result, and moves the money.

## How It Works

```
 Deploy                   Compete                   Settle
 ──────                   ───────                   ──────
 Users train agents       Platform executes          Solana program
 on their own GPUs        matches server-side        escrows & resolves

       │                        │                         │
       ▼                        ▼                         ▼
 Upload checkpoint ──► Matchmaker pairs by Elo ──► Smart contract
                              │                     manages wagering
                              ▼
                     Deterministic execution
                     streamed live via WebSocket
                     (video @ 30fps + data @ 10Hz)
```

### Agent Lifecycle

1. **Train** — Bring your own GPUs. Use stable-retro + SB3 (PPO) or any RL framework
2. **Upload** — Submit model checkpoint via the agent gateway API
3. **Calibrate** — Platform runs matches against reference bots to seed Elo rating
4. **Compete** — Agent enters ranked matchmaking queue, fights autonomously at its skill level
5. **Earn** — Agent owners and spectators wager SOL on outcomes

### On-Chain Settlement

```
 Place Wager ──► Match Executes ──► Result Hashed ──► Oracle Resolves ──► Auto-Payout
     │                                                                        │
     ▼                                                                        ▼
  SOL escrowed            Oracle signs winner                      Winners claim
  in vault PDA            to smart contract                        from vault
```

Every match produces a cryptographic hash of the full game state before settlement. Wagering pools are Solana PDAs — SOL is escrowed in a program-owned vault at bet time. The oracle submits the verified result on-chain. Winners withdraw proportional payouts. Cancelled matches refund automatically.

No custody. No middleman. Code settles.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14)                                           │
│  Arena Viewer + Wagering UI + Solana Wallet Adapter              │
├──────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)              │  Workers (Celery)               │
│  REST API + Agent Gateway       │  Match Engine + Scheduler       │
│  WebSocket Streaming            │  Elo Calibration + Seasonal     │
├─────────────────────────────────┼────────────────────────────────┤
│  Execution Layer                │  Settlement Layer (Anchor)      │
│  Deterministic game engine      │  MatchPool, Bet, PlatformConfig │
│  Pluggable environment adapters │  Escrow, Payout, Refund         │
├──────────────────────────────────────────────────────────────────┤
│  PostgreSQL    Redis    MinIO (S3)    Solana                     │
└──────────────────────────────────────────────────────────────────┘
```

## Core Infrastructure

- **Deterministic Execution** — Server-side match engine with hashed, reproducible outcomes
- **On-Chain Settlement** — Solana program handles escrow, payout, and refunds with no custody
- **Skill-Based Matchmaking** — Elo rating system with calibration, K-factor tiers, and seasonal resets
- **Live Streaming** — Binary JPEG video + structured JSON data channels over WebSocket
- **Pluggable Environments** — Game adapter interface for any competitive AI environment
- **Replay Integrity** — Every match hashed, recorded, and archived to S3 before on-chain resolution
- **Decentralized Training** — No vendor lock-in. Users train on their own compute, platform only executes

## First Vertical: Fighting Games

The launch environment is classic fighting games via stable-retro emulation:

- **SF2 Champion Edition** (Genesis) — primary launch title
- **SF3 3rd Strike**, **KOF 98**, **Tekken Tag** — additional adapters
- Pluggable adapter system: implement `extract_state()`, `is_round_over()`, `is_match_over()` for any new game

The adapter interface is intentionally simple — the same infrastructure can host chess engines, card game AI, strategy bots, or any environment that produces a deterministic winner.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Zustand, Solana wallet-adapter |
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async), Celery, Redis |
| Execution | stable-retro, OpenCV, pluggable game adapters |
| Settlement | Solana, Anchor 0.30, solana-py, solders |
| Infrastructure | PostgreSQL, Redis, MinIO (S3-compatible), Docker Compose |

## Project Structure

```
packages/
  backend/        Execution engine, API, matchmaking, Solana integration
  frontend/       Arena viewer, wagering UI, wallet connection
  contracts/      Solana Anchor program — wagering pools, settlement, platform config
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

# Initialize platform config
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

## References

Built on top of these open-source projects and research:

**Emulation & RL**

- [stable-retro](https://github.com/Farama-Foundation/stable-retro) — Genesis/arcade emulation environments for RL
- [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) — PPO implementation, CnnPolicy, VecFrameStack
- [linyiLYi/street-fighter-ai](https://github.com/linyiLYi/street-fighter-ai) — Asymmetric reward shaping, exponential round bonuses
- [FightLadder (ICML 2024)](https://github.com/FightLadder/fightladder) — Competitive AI evaluation and Elo-based ranking for fighting game agents
- [Mnih et al. "Playing Atari with Deep RL"](https://arxiv.org/abs/1312.5602) — 84x84 grayscale preprocessing, 4-frame stacking
- [OpenAI Retro Contest](https://openai.com/index/retro-contest/) — Retro game RL benchmarks and environment design

**On-Chain Settlement**

- [Anchor](https://github.com/coral-xyz/anchor) — Solana smart contract framework
- [solana-py](https://github.com/michaelhly/solana-py) — Python client for Solana RPC
- [Solana wallet-adapter](https://github.com/anza-xyz/wallet-adapter) — Frontend wallet integration

**Infrastructure**

- [FastAPI](https://github.com/fastapi/fastapi) — Async Python API
- [Next.js](https://github.com/vercel/next.js) — React framework (App Router)
- [Celery](https://github.com/celery/celery) — Distributed task queue
- [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) — Async ORM
- [Zustand](https://github.com/pmndrs/zustand) — Frontend state management
