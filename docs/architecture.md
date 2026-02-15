# Rawl Platform — Architecture Guide

**Last updated:** 2026-02-15

---

## System Overview

Rawl is an AI fighting game platform where users train reinforcement learning agents, match them against each other in real-time, and bet on outcomes using Solana. The platform consists of four packages in a monorepo:

```
packages/
  backend/     Python (FastAPI + Celery) — API, match engine, training pipeline
  frontend/    Next.js 14 (App Router) — spectator UI, wallet integration
  contracts/   Solana Anchor — betting pools, payouts, match resolution
  shared/      TypeScript — shared types between frontend and contracts
```

---

## Architecture Diagram

```
                          ┌──────────────────────────┐
                          │     Next.js Frontend      │
                          │  (Lobby, Arena, Dashboard) │
                          └─────┬────────────┬────────┘
                                │            │
                       REST API │    WebSocket│ (video + data)
                                │            │
                    ┌───────────▼────────────▼─────────────┐
                    │         FastAPI Backend               │
                    │                                       │
                    │  ┌─────────┐  ┌───────────┐          │
                    │  │   API   │  │  Gateway   │          │
                    │  │ (public)│  │(auth'd API)│          │
                    │  └────┬────┘  └─────┬──────┘          │
                    │       │             │                  │
                    │  ┌────▼─────────────▼──────┐          │
                    │  │      Services Layer      │          │
                    │  │ (Elo, Queue, Scheduler)  │          │
                    │  └──────────┬───────────────┘          │
                    │             │                          │
                    │  ┌──────────▼──────────┐               │
                    │  │   Match Engine       │               │
                    │  │ (DIAMBRA, Models)    │               │
                    │  └──────────┬──────────┘               │
                    └─────────────┼───────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │      Celery Workers         │
                    │  (match exec, training,     │
                    │   validation, scheduling)   │
                    └─────┬───────────┬───────────┘
                          │           │
               ┌──────────▼──┐  ┌────▼──────────┐
               │  PostgreSQL  │  │    Redis       │
               │  (state)     │  │  (cache, queue,│
               │              │  │   streams)     │
               └──────────────┘  └───────────────┘
                          │
               ┌──────────▼──────────┐
               │   Solana Blockchain  │
               │  (betting pools,     │
               │   match resolution)  │
               └──────────────────────┘
```

---

## Backend Architecture

### Layer Structure

```
rawl/
├── api/                    # Public REST API (unauthenticated)
│   └── routes/
│       ├── matches.py      # GET /api/matches, /api/matches/{id}
│       ├── fighters.py     # GET /api/fighters, /api/fighters/{id}
│       ├── odds.py         # GET /api/matches/{id}/odds
│       ├── leaderboard.py  # GET /api/leaderboard/{game_id}
│       └── internal.py     # GET /api/health, /api/metrics
│
├── gateway/                # Authenticated API (requires X-API-Key)
│   ├── auth.py             # HMAC-SHA256 API key, Ed25519 signature verification
│   ├── schemas.py          # Pydantic request/response models
│   └── routes/
│       ├── register.py     # POST /gateway/register
│       ├── submit.py       # POST /gateway/submit (rate limited: 3/wallet/hr)
│       ├── training.py     # POST /gateway/train, GET /train/{id}, POST /train/{id}/stop
│       ├── match.py        # POST /gateway/queue, POST /gateway/match
│       ├── fighters.py     # GET /gateway/fighters
│       └── leaderboard.py  # GET /gateway/leaderboard/{game_id}
│
├── engine/                 # Match execution engine
│   ├── match_runner.py     # Full game loop (DIAMBRA + model inference)
│   ├── diambra_manager.py  # DIAMBRA arena lifecycle management
│   ├── model_loader.py     # S3 download + PPO.load() + cache
│   ├── oracle_client.py    # Solana tx submission (lock/resolve/cancel)
│   ├── match_result.py     # Canonical JSON hashing, tiebreaker logic
│   ├── frame_processor.py  # RGB -> grayscale 128x128, MJPEG encoding
│   ├── replay_recorder.py  # MJPEG + JSON sidecar recording
│   ├── field_validator.py  # Consecutive/total threshold detection
│   ├── failed_upload_handler.py  # S3 dead-letter + retry
│   └── tasks.py            # Celery tasks (execute_match, retry_uploads)
│
├── training/               # Training pipeline
│   ├── validation.py       # 4-step model validation
│   ├── worker.py           # PPO training with progress streaming
│   ├── self_play.py        # Self-play callback with checkpoint pool
│   └── pipeline.py         # PPO hyperparameter config
│
├── game_adapters/          # Per-game state extraction
│   ├── base.py             # GameAdapter ABC (extract_state, is_round_over, is_match_over)
│   ├── sfiii3n.py          # Street Fighter III 3rd Strike (MAX_HEALTH=176)
│   ├── kof98.py            # King of Fighters 98 (MAX_HEALTH=103, TEAM_SIZE=3)
│   ├── tektagt.py          # Tekken Tag Tournament (MAX_HEALTH=170, tag)
│   ├── umk3.py             # Ultimate Mortal Kombat 3 (stub)
│   └── doapp.py            # Dead or Alive ++ (stub)
│
├── solana/                 # Solana blockchain integration
│   ├── client.py           # AsyncClient with retry/backoff
│   ├── pda.py              # PDA derivation (4 functions)
│   ├── deserialize.py      # Account deserialization (MatchPool, Bet, PlatformConfig)
│   ├── instructions.py     # 15 instruction builders
│   └── account_listener.py # WebSocket programSubscribe + DB sync
│
├── services/               # Business logic services
│   ├── elo.py              # Adaptive K-factor Elo (calibration, divisions)
│   ├── match_queue.py      # Redis sorted-set Elo-proximity matchmaking
│   ├── match_scheduler.py  # Celery Beat: pair fighters, dispatch matches
│   ├── anti_manipulation.py # Betting concentration, cross-wallet analysis
│   ├── health_checker.py   # Match heartbeat monitoring
│   └── agent_registry.py   # Fighter model path lookup
│
├── ws/                     # WebSocket streaming
│   ├── broadcaster.py      # Video (binary JPEG) + Data (JSON) channels
│   └── training_ws.py      # Training progress stream
│
├── monitoring/             # Observability
│   ├── health_checks.py    # 8 health checks
│   ├── metrics.py          # Prometheus counters/gauges/histograms
│   └── logging_config.py   # structlog JSON with trace IDs
│
├── db/                     # Database layer
│   ├── session.py          # async SQLAlchemy engine + session factory
│   └── models/             # 7 SQLAlchemy models
│       ├── user.py
│       ├── match.py
│       ├── bet.py
│       ├── fighter.py
│       ├── training_job.py
│       ├── calibration_match.py
│       └── failed_upload.py
│
├── config.py               # Pydantic Settings (env vars)
├── main.py                 # FastAPI app factory + lifespan
├── celery_app.py           # Celery config + Beat schedule
├── redis_client.py         # Redis connection pool
├── s3_client.py            # Async S3 client (aiobotocore)
└── dependencies.py         # FastAPI dependency injection
```

---

## Data Flow: Match Execution

```
1. Fighter A queued  ──────────┐
                               ├──> Match Queue (Redis sorted set)
2. Fighter B queued  ──────────┘
                                        │
3. Match Scheduler (Celery Beat, 10s) ──┘
   Pairs by Elo proximity (+/-200, widens +50/tick)
                                        │
4. Creates Match DB record  ◄───────────┘
   Dispatches execute_match Celery task
                                        │
5. Match Runner ◄───────────────────────┘
   a. Load models from S3 (PPO.load)
   b. Start DIAMBRA container
   c. Lock match on-chain (oracle tx)
   d. Game loop:
      - model.predict(obs) -> actions
      - env.step(actions) -> obs, reward, done, info
      - adapter.extract_state(info) -> health, round, timer
      - Publish JPEG frame to Redis stream (30fps)
      - Publish data JSON to Redis stream (10Hz)
      - Check is_round_over / is_match_over
   e. Hash result (SHA-256 canonical JSON)
   f. Upload replay to S3
   g. Resolve match on-chain (oracle tx)
                                        │
6. Post-match ◄─────────────────────────┘
   - Update Elo ratings (adaptive K-factors)
   - Set Match status to "resolved"
   - Account listener detects on-chain change
   - Bettors can claim payouts
```

---

## Data Flow: Training Pipeline

```
1. POST /gateway/submit (model S3 key)
   Rate limited: 3/wallet/hour
                     │
2. Validation (Celery task)
   a. PPO.load() — file integrity
   b. Action space check — 100 random obs
   c. Latency check — p99 < 5ms
   d. Docker sandbox — no network, read-only
   Fighter status: validating -> ready/rejected
                     │
3. POST /gateway/train
   Tier enforcement (free/standard/pro)
   Concurrent job limit check
                     │
4. Training Worker (Celery task)
   a. Create DIAMBRA env (vectorized)
   b. PPO.learn(total_timesteps)
   c. ProgressCallback every 10K steps -> Redis stream
   d. Save model to S3
   e. Update Fighter.model_path
   Job status: queued -> running -> completed/failed
                     │
5. WebSocket /ws/gateway/train/{job_id}
   Streams progress from Redis to frontend
```

---

## Solana Integration

### On-Chain State

| Account | Seeds | Key Fields |
|---------|-------|------------|
| `PlatformConfig` | `b"platform_config"` | authority, oracle, fee_bps, treasury, paused, match_timeout |
| `MatchPool` | `b"match_pool" + match_id` | match_id, fighters, pool totals, bet counts, status, winner, min_bet, betting_window |
| `Bet` | `b"bet" + match_id + bettor` | bettor, match_id, side, amount, claimed |
| `Vault` | `b"vault" + match_id` | (system account holding SOL) |

### Instruction Flow

```
create_match ──> place_bet (multiple) ──> lock_match ──> resolve_match ──> claim_payout
                                              │                              (per winner)
                                              │
                                         cancel_match ──> refund_bet
                                              │             (per bettor)
                                              │
                                         timeout_match ──> refund_bet
```

### Backend-Chain Sync

The `AccountListener` maintains a WebSocket `programSubscribe` connection:
- Detects MatchPool status changes -> updates Match DB record
- Detects Bet claims -> updates Bet DB record
- On reconnect: `getProgramAccounts` for full reconciliation

---

## Frontend Architecture

### Pages

| Route | Component | Auth | Description |
|-------|-----------|------|-------------|
| `/` | `page.tsx` | No | Landing page |
| `/lobby` | `lobby/page.tsx` | No | Match browser with status filters |
| `/arena/[matchId]` | `arena/[matchId]/page.tsx` | No | Live match viewer + betting |
| `/leaderboard` | `leaderboard/page.tsx` | No | Rankings by game |
| `/fighters/[fighterId]` | `fighters/[fighterId]/page.tsx` | No | Fighter profile + stats |
| `/dashboard` | `dashboard/page.tsx` | Wallet | User's fighters + queue management |

### State Management

- **Zustand stores**: `matchStore` (match state), `walletStore` (API key, wallet)
- **localStorage**: API key and wallet address persisted across sessions
- **WebSocket hooks**: `useMatchVideoStream` (binary JPEG), `useMatchDataStream` (JSON)

### Wallet Integration

- Solana Wallet Adapter: Phantom, Solflare
- Configurable RPC endpoint and network via env vars
- `WalletMultiButton` in navbar for connect/disconnect

---

## Infrastructure

### Docker Compose (Local Development)

| Service | Image | Port |
|---------|-------|------|
| PostgreSQL | postgres:16 | 5432 |
| Redis | redis:7 | 6379 |
| MinIO | minio/minio | 9000 |

### Celery Beat Schedule

| Task | Interval | Purpose |
|------|----------|---------|
| `check_match_heartbeats` | 15s | Auto-cancel stale matches (60s timeout) |
| `schedule_pending_matches` | 10s | Pair queued fighters, dispatch matches |
| `retry_failed_uploads_task` | 5min | Retry failed S3 uploads (up to 5 attempts) |

### Health Checks (`GET /api/health`)

| Check | Timeout | What it Tests |
|-------|---------|---------------|
| database | - | `SELECT 1` via async engine |
| redis | - | `PING` command |
| s3 | - | `head_bucket` on configured bucket |
| celery | 2s | Worker ping via inspector |
| solana_rpc | - | `get_health()` on RPC endpoint |
| diambra | 5s | `docker image inspect` for engine image |
| match_queue | - | Count active game queues |
| active_matches | - | Count pending/running matches |

---

## Key Technical Decisions

1. **Cursor-based pagination** — All list endpoints use base64-encoded `(created_at, id)` cursors instead of offset-based pagination for consistency and performance.

2. **Redis sorted sets for matchmaking** — Elo ratings as scores enable O(log N) proximity matching with `ZRANGEBYSCORE`, with progressive window widening to avoid indefinite queuing.

3. **Canonical JSON hashing** — Match results are hashed with sorted keys, no whitespace, and a `hash_version` field for forward compatibility.

4. **Oracle pattern** — The backend holds a keypair that signs on-chain transactions. The oracle is the only entity authorized to lock/resolve/cancel matches, preventing front-running.

5. **Parimutuel betting** — Pool-based (not fixed-odds). Odds shift as bets come in. Platform takes 3% fee. Winners split the entire pool proportionally.

6. **SB3 PPO** — All fighter models use Stable Baselines 3 PPO with MultiInputPolicy. This ensures model format consistency across the platform.
