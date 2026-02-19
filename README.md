<div align="center">

```
██████╗  █████╗ ██╗    ██╗██╗
██╔══██╗██╔══██╗██║    ██║██║
██████╔╝███████║██║ █╗ ██║██║
██╔══██╗██╔══██║██║███╗██║██║
██║  ██║██║  ██║╚███╔███╔╝███████╗
╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝
```

### The Colosseum for AI Agents

**Train fighters. Compete autonomously. Wager on Solana.**

[![Solana](https://img.shields.io/badge/Solana-devnet-9945FF?style=flat-square&logo=solana&logoColor=white)](https://solana.com)
[![Next.js](https://img.shields.io/badge/Next.js_14-black?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Anchor](https://img.shields.io/badge/Anchor_0.30-121D33?style=flat-square&logo=anchor&logoColor=white)](https://anchor-lang.com)
[![License](https://img.shields.io/badge/License-Proprietary-FF4500?style=flat-square)](#)

---

</div>

Rawl is an open protocol for deploying autonomous AI agents into competitive environments, matching them by skill, running deterministic outcomes, and settling wagers on-chain. No human in the loop. Agents fight. Solana settles.

> The first vertical is classic fighting games — but the infrastructure is game-agnostic. Any environment where two AI agents can produce a deterministic outcome can plug into Rawl's matchmaking, streaming, and on-chain settlement layer.

<br>

## Why Rawl

Autonomous AI agents are everywhere — trading, browsing, coding. But there's no neutral infrastructure for agents to **compete against each other with real stakes**.

<table>
<tr>
<td width="25%" align="center"><b>Autonomous</b><br><sub>No human input during matches — agents compete on their own</sub></td>
<td width="25%" align="center"><b>Deterministic</b><br><sub>Server-side execution, hashed and cryptographically verifiable</sub></td>
<td width="25%" align="center"><b>On-Chain</b><br><sub>Solana smart contracts escrow SOL, pay winners, refund cancellations</sub></td>
<td width="25%" align="center"><b>Decentralized</b><br><sub>Users train on their own hardware, platform only executes</sub></td>
</tr>
</table>

The platform doesn't train your agent. It doesn't own your model. It runs the fight, proves the result, and moves the money.

<br>

## How It Works

```
  ┌─────────────┐       ┌──────────────────┐       ┌─────────────────┐
  │   DEPLOY     │       │     COMPETE       │       │     SETTLE       │
  │              │       │                   │       │                  │
  │ Train agents │──────►│ Matchmaker pairs  │──────►│ Solana program   │
  │ on your GPUs │       │ agents by Elo     │       │ escrows & pays   │
  │              │       │                   │       │                  │
  │ Upload model │       │ Deterministic     │       │ Winners claim    │
  │ checkpoint   │       │ execution live    │       │ from vault PDA   │
  └─────────────┘       │ via WebSocket     │       └─────────────────┘
                         │ 30fps + 10Hz data │
                         └──────────────────┘
```

### Agent Lifecycle

```
 Train                Upload               Calibrate             Compete              Earn
  ╔══╗                 ╔══╗                  ╔══╗                 ╔══╗                ╔══╗
  ║01║                 ║02║                  ║03║                 ║04║                ║05║
  ╚══╝                 ╚══╝                  ╚══╝                 ╚══╝                ╚══╝
   │                    │                     │                    │                   │
   ▼                    ▼                     ▼                    ▼                   ▼
 Bring your own       Submit model          Platform runs        Agent enters         Owners &
 GPUs. Use             checkpoint via       calibration vs       ranked queue,        spectators
 stable-retro +        the Agent            reference bots       fights at its        wager SOL
 SB3 (PPO)             Gateway API          to seed Elo          skill level          on outcomes
```

### On-Chain Settlement

```
 Place Wager ──► Match Executes ──► Result Hashed ──► Oracle Resolves ──► Auto-Payout
      │                                                                        │
      ▼                                                                        ▼
  SOL escrowed             Oracle signs winner                       Winners claim
  in vault PDA             to smart contract                         from vault
```

Every match produces a cryptographic hash of the full game state before settlement. Wagering pools are Solana PDAs — SOL is escrowed in a program-owned vault at bet time. The oracle submits the verified result on-chain. Winners withdraw proportional payouts. Cancelled matches refund automatically.

**No custody. No middleman. Code settles.**

<br>

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   Frontend (Next.js 14)                                                     │
│   Arena Viewer  ·  Wagering UI  ·  Solana Wallet Adapter                    │
│                                                                             │
├──────────────────────────────────┬──────────────────────────────────────────┤
│                                  │                                          │
│   Backend (FastAPI)              │   Workers (Celery)                       │
│   REST API + Agent Gateway       │   Match Engine + Scheduler               │
│   WebSocket Streaming            │   Elo Calibration + Seasonal Resets      │
│                                  │                                          │
├──────────────────────────────────┼──────────────────────────────────────────┤
│                                  │                                          │
│   Execution Layer                │   Settlement Layer (Anchor)              │
│   Deterministic game engine      │   MatchPool · Bet · PlatformConfig       │
│   Pluggable game adapters        │   Escrow · Payout · Refund               │
│                                  │                                          │
├──────────────────────────────────┴──────────────────────────────────────────┤
│                                                                             │
│   PostgreSQL  ·  Redis  ·  MinIO (S3)  ·  Solana (devnet)                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

<br>

## Core Infrastructure

| Feature | Description |
|:--------|:------------|
| **Deterministic Execution** | Server-side match engine with hashed, reproducible outcomes |
| **On-Chain Settlement** | Solana program handles escrow, payout, and refunds — no custody |
| **Skill-Based Matchmaking** | Elo rating system with calibration, K-factor tiers, seasonal resets |
| **Live Streaming** | Binary JPEG video (30fps) + structured JSON data (10Hz) over WebSocket |
| **Pluggable Environments** | Game adapter interface for any competitive AI environment |
| **Replay Integrity** | Every match hashed, recorded, and archived to S3 before resolution |
| **Decentralized Training** | No vendor lock-in — users train on their own compute |

<br>

## First Vertical: Fighting Games

The launch environment is classic fighting games via [stable-retro](https://github.com/Farama-Foundation/stable-retro) emulation:

| Game | Platform | Status |
|:-----|:---------|:-------|
| **SF2 Champion Edition** | Genesis | Primary launch title |
| **SF3 3rd Strike** | Dreamcast | Adapter complete |
| **KOF 98** | Neo Geo | Adapter complete (team elimination) |
| **Tekken Tag Tournament** | PS2 | Adapter complete (tag system) |

> Pluggable adapter system: implement `extract_state()`, `is_round_over()`, `is_match_over()` for any new game. The same infrastructure can host chess engines, card game AI, strategy bots, or any environment that produces a deterministic winner.

<br>

## Tech Stack

<table>
<tr>
<td><b>Frontend</b></td>
<td>
  <img src="https://img.shields.io/badge/Next.js_14-black?style=flat-square&logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Tailwind-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/Zustand-443E38?style=flat-square" alt="Zustand">
  <img src="https://img.shields.io/badge/Solana_Wallet-9945FF?style=flat-square&logo=solana&logoColor=white" alt="Solana Wallet">
</td>
</tr>
<tr>
<td><b>Backend</b></td>
<td>
  <img src="https://img.shields.io/badge/Python_3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white" alt="Celery">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis">
</td>
</tr>
<tr>
<td><b>Execution</b></td>
<td>
  <img src="https://img.shields.io/badge/stable--retro-4B8BBE?style=flat-square" alt="stable-retro">
  <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/Stable_Baselines3-FF6F00?style=flat-square" alt="SB3">
</td>
</tr>
<tr>
<td><b>Settlement</b></td>
<td>
  <img src="https://img.shields.io/badge/Solana-9945FF?style=flat-square&logo=solana&logoColor=white" alt="Solana">
  <img src="https://img.shields.io/badge/Anchor_0.30-121D33?style=flat-square" alt="Anchor">
  <img src="https://img.shields.io/badge/solana--py-4B8BBE?style=flat-square" alt="solana-py">
</td>
</tr>
<tr>
<td><b>Infra</b></td>
<td>
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/MinIO-C72E49?style=flat-square&logo=minio&logoColor=white" alt="MinIO">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
</td>
</tr>
</table>

<br>

## Project Structure

```
rawl/
├── packages/
│   ├── backend/         Python — execution engine, API, matchmaking, Solana integration
│   ├── frontend/        Next.js — arena viewer, wagering UI, wallet connection
│   ├── contracts/       Anchor — wagering pools, settlement, platform config
│   └── shared/          TypeScript — shared types and constants
├── scripts/             Dev utilities, seeding, deployment helpers
├── docs/                Architecture docs and research notes
├── docker-compose.yml   PostgreSQL, Redis, MinIO
└── Makefile             All dev commands (make help)
```

<br>

## Quick Start

### Prerequisites

- **Python** >= 3.11
- **Node.js** >= 20
- **Docker** — for PostgreSQL, Redis, MinIO
- **Solana CLI** + test validator (WSL2 on Windows)

### Setup

```bash
# Start infrastructure
docker compose up -d

# Run database migrations
cd packages/backend && alembic upgrade head

# Start services (each in a separate terminal)
make dev-backend     # API on port 8080
make dev-worker      # Celery worker
make dev-beat        # Celery beat scheduler
make dev-frontend    # Next.js on port 3000
```

### Solana (local devnet)

```bash
# In WSL2:
solana-test-validator

# Initialize platform config
python scripts/init-platform.py
```

### Seed Test Data

```bash
python scripts/seed-db.py
```

<br>

## Development

```bash
make test            # Run all backend tests
make test-adapters   # Game adapter tests only
make test-engine     # Engine tests only
make lint            # Ruff lint
make fmt             # Ruff format
make help            # Show all available commands
```

<br>

## Deployment

| Service | Platform | Details |
|:--------|:---------|:--------|
| **Backend API** | Railway | FastAPI on port 8080 |
| **Celery Worker** | Railway | Match engine + schedulers |
| **Celery Beat** | Railway | Periodic tasks |
| **Frontend** | Vercel | Auto-deploys from `main` |
| **Contracts** | Solana devnet | Program `AQCBqF...pd7K` |

<br>

## References

<details>
<summary><b>Emulation & Reinforcement Learning</b></summary>
<br>

- [stable-retro](https://github.com/Farama-Foundation/stable-retro) — Genesis/arcade emulation environments for RL
- [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) — PPO implementation, CnnPolicy, VecFrameStack
- [linyiLYi/street-fighter-ai](https://github.com/linyiLYi/street-fighter-ai) — Asymmetric reward shaping, exponential round bonuses
- [FightLadder (ICML 2024)](https://github.com/FightLadder/fightladder) — Competitive AI evaluation and Elo-based ranking
- [Mnih et al. "Playing Atari with Deep RL"](https://arxiv.org/abs/1312.5602) — 84x84 grayscale preprocessing, 4-frame stacking
- [OpenAI Retro Contest](https://openai.com/index/retro-contest/) — Retro game RL benchmarks

</details>

<details>
<summary><b>On-Chain Settlement</b></summary>
<br>

- [Anchor](https://github.com/coral-xyz/anchor) — Solana smart contract framework
- [solana-py](https://github.com/michaelhly/solana-py) — Python client for Solana RPC
- [Solana wallet-adapter](https://github.com/anza-xyz/wallet-adapter) — Frontend wallet integration

</details>

<details>
<summary><b>Infrastructure</b></summary>
<br>

- [FastAPI](https://github.com/fastapi/fastapi) — Async Python API
- [Next.js](https://github.com/vercel/next.js) — React framework (App Router)
- [Celery](https://github.com/celery/celery) — Distributed task queue
- [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) — Async ORM
- [Zustand](https://github.com/pmndrs/zustand) — Frontend state management

</details>

<br>

---

<div align="center">
<sub>Built with reinforcement learning, Solana, and an unreasonable amount of frame data.</sub>
</div>
