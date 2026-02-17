# Rawl Platform — Full SDD Implementation Plan

> **Historical document** from 2026-02-15. All 8 phases have been completed. See `implementation_completion_report.md` for results and `launch_roadmap.md` for current status.

**Date:** 2026-02-15
**SDD Version:** v2.6.0 (`Rawl_SDD.md`)

## Context

The SDD audit found the codebase is ~40-50% complete. Strong foundations exist (DB models, auth, Elo, game adapters, contracts) but critical runtime paths are stubbed/commented. This plan closes all gaps in 8 dependency-ordered phases, following existing codebase patterns exactly.

## Phase Dependency Graph

```
Phase 0: Schema & Config ──────────────────────────────┐
    │                                                   │
    v                                                   v
Phase 1: Solana Client ──> Phase 2: Oracle & Listener   Phase 4: Training
    │                          │                            │
    └──────────────────────────┘                            │
                │                                           │
                v                                           │
          Phase 3: Match Engine ────────────────────────────┘
                │                                           │
                v                                           v
          Phase 5: Gateway Wiring & Queue ──> Phase 6: Monitoring
                │                                           │
                └───────────────────────────────────────────┘
                                    │
                                    v
                          Phase 7: Frontend
                                    │
                                    v
                      Phase 8: Contract Enhancements
```

---

## Phase 0: Schema & Config Foundation

**Goal:** Add missing DB columns and config fields so all subsequent phases have correct schema.

### Task 0.1 — Add missing DB model fields
- **Modify** `packages/backend/src/rawl/db/models/bet.py` — add `claimed_at: Mapped[datetime | None]`
- **Modify** `packages/backend/src/rawl/db/models/fighter.py` — add `division_tier: Mapped[str]` (default "Bronze")
- **Modify** `packages/backend/src/rawl/db/models/training_job.py` — add `tier`, `gpu_type`, `queue_position`

### Task 0.2 — Add config fields
- **Modify** `packages/backend/src/rawl/config.py` — add training tier limits, stable-retro settings, `solana_confirm_timeout`, `solana_max_retries`

### Task 0.3 — Alembic migration
- **Create** `packages/backend/alembic/versions/002_add_missing_fields.py`

### Verify
- `alembic upgrade head` succeeds
- `pytest` still passes

---

## Phase 1: Solana Backend Client

**Goal:** Full RPC client with PDA derivation, account deserialization, instruction building, and transaction submission.

### Task 1.1 — PDA derivation module
- **Create** `packages/backend/src/rawl/solana/pda.py`
- Functions: `derive_platform_config_pda`, `derive_match_pool_pda`, `derive_bet_pda`, `derive_vault_pda`
- Seeds match contract: `b"platform_config"`, `b"match_pool" + match_id`, `b"bet" + match_id + bettor`, `b"vault" + match_id`
- Helper: `match_id_to_bytes(uuid_str) -> bytes` using `uuid.UUID(id).bytes.ljust(32, b'\x00')`

### Task 1.2 — Account deserialization
- **Create** `packages/backend/src/rawl/solana/deserialize.py`
- `deserialize_match_pool(data)` — 238 bytes: 8 discriminator + 18 fields via `struct.unpack_from()`
- `deserialize_bet(data)` — 84 bytes: 8 discriminator + 6 fields
- `deserialize_platform_config(data)` — 116 bytes: 8 discriminator + 7 fields
- Results as `@dataclass` objects

### Task 1.3 — Instruction builders
- **Create** `packages/backend/src/rawl/solana/instructions.py`
- Build `solders.instruction.Instruction` for all 14 instructions
- Anchor discriminators: `SHA256("global:<name>")[:8]`
- Account metas with correct `is_signer`/`is_writable` flags matching Anchor `#[derive(Accounts)]` structs

### Task 1.4 — Full SolanaClient implementation
- **Modify** `packages/backend/src/rawl/solana/client.py` — replace stub
- `initialize()` — create `AsyncClient`, load oracle keypair
- `send_and_confirm_tx()` — retry with backoff, Prometheus metrics
- `get_match_pool()`, `get_bet()`, `get_platform_config()` — PDA lookup + deserialize
- `create_match_on_chain()`, `lock_match_on_chain()`, `resolve_match_on_chain()`, `cancel_match_on_chain()`

### Task 1.5 — Tests
- **Create** `packages/backend/tests/test_solana/test_pda.py` — deterministic PDA derivation
- **Create** `packages/backend/tests/test_solana/test_deserialize.py` — known byte patterns

---

## Phase 2: Oracle Client & Account Listener

**Goal:** Wire oracle to submit real Solana txs; implement account listener for on-chain event detection.

### Task 2.1 — Implement oracle client
- **Modify** `packages/backend/src/rawl/engine/oracle_client.py` — replace `NotImplementedError`
- `submit_lock(match_id)` — build `lock_match_ix`, sign with oracle, send via `solana_client`
- `submit_resolve(match_id, winner, match_hash)` — convert "P1"/"P2" to u8, build `resolve_match_ix`
- `submit_cancel(match_id, reason)` — build `cancel_match_ix`
- Retry up to `settings.solana_max_retries` with backoff [1, 2, 4]s

### Task 2.2 — Implement account listener
- **Modify** `packages/backend/src/rawl/solana/account_listener.py` — replace scaffold
- `_connect_and_listen()` — WebSocket `programSubscribe` for `settings.program_id`
- `_handle_message()` — discriminator check → deserialize MatchPool or Bet → update PostgreSQL
- `_catch_up()` — `getProgramAccounts` RPC for reconciliation on reconnect
- Exponential backoff reconnect (already scaffolded: INITIAL_BACKOFF=1, MAX_BACKOFF=30)

### Task 2.3 — Register in app lifespan
- **Modify** `packages/backend/src/rawl/main.py`
- Startup: `await solana_client.initialize()`, `asyncio.create_task(account_listener.start())`
- Shutdown: `account_listener.stop()`, `await solana_client.close()`

---

## Phase 3: Match Engine (Game Loop)

**Goal:** Implement the match runner game loop with RetroEngine (stable-retro), model loading, frame publishing.

### Task 3.1 — Implement EmulationEngine + RetroEngine
- **Create** `packages/backend/src/rawl/engine/emulation/base.py` — `EmulationEngine` ABC
- **Create** `packages/backend/src/rawl/engine/emulation/retro_engine.py` — wraps stable-retro (genesis_plus_gx core, SF2 Genesis), translates flat→nested formats for adapter compatibility
- **Delete** `packages/backend/src/rawl/engine/diambra_manager.py`

### Task 3.2 — Model loader
- **Create** `packages/backend/src/rawl/engine/model_loader.py`
- `load_fighter_model(s3_key, game_id)` — download from S3, `SB3.PPO.load()`, validate action space
- In-memory cache by S3 key

### Task 3.3 — Wire match runner game loop
- **Modify** `packages/backend/src/rawl/engine/match_runner.py` — uncomment lines 79-220
- Load models → start RetroEngine → validate info → lock match (oracle) → game loop:
  - Get actions from both models via `model.predict()`
  - Step environment
  - Extract state via adapter (`extract_state`, `is_round_over`, `is_match_over`)
  - Publish JPEG frame to Redis stream (video channel)
  - Publish data JSON at 10Hz (data channel)
  - Record replay frame
  - Heartbeat every 15s
- Post-loop: hash result → S3 upload → oracle resolve → return MatchResult

### Task 3.4 — Failed upload dead-letter
- **Create** `packages/backend/src/rawl/engine/failed_upload_handler.py`
- `persist_failed_upload()` — create `FailedUpload` row
- `retry_failed_uploads()` — Celery Beat task (every 5 min), retry S3 uploads

### Task 3.5 — Match execution Celery task
- **Create** `packages/backend/src/rawl/engine/tasks.py`
- `execute_match(match_id, game_id, fighter_a_model, fighter_b_model, match_format)`
- Sync wrapper → `asyncio.run()` (follows existing pattern in `health_checker.py`)
- On success: update Elo via `services/elo.py`, update Match status

---

## Phase 4: Training Pipeline

**Goal:** Real validation, PPO training with progress streaming, tiers, self-play.

### Task 4.1 — Implement validation (4 steps)
- **Modify** `packages/backend/src/rawl/training/validation.py` — uncomment all 4 steps
- Step 1: `SB3.load()` in try/except
- Step 2: 100 random observations → verify MultiDiscrete output shape
- Step 3: 100 inference steps → reject if p99 > 5ms
- Step 4: Docker sandbox (no network, read-only FS, 60s timeout)
- Status transitions: validating → ready/rejected

### Task 4.2 — Training moved off-platform
- **Modify** `packages/backend/src/rawl/training/worker.py` — gutted, raises `NotImplementedError`
- Training is off-platform: users rent GPUs and run the open-source `rawl-trainer` package
- Platform only validates submitted checkpoints (Task 4.1)

### Task 4.3 — Training tier enforcement
- **Modify** `packages/backend/src/rawl/gateway/routes/training.py` — validate tier limits
- Add `POST /train/{job_id}/stop` endpoint

### Task 4.5 — Register training WS
- **Modify** `packages/backend/src/rawl/main.py` — add `training_ws_router`

---

## Phase 5: Gateway Wiring & Match Queue

**Goal:** Activate all commented-out dispatches, Elo-proximity matching, missing endpoints, rate limiting.

### Task 5.1 — Uncomment Celery dispatches
- **Modify** `gateway/routes/training.py` — uncomment `run_training.delay()`
- **Modify** `gateway/routes/submit.py` — uncomment `validate_model.delay()`
- **Modify** `gateway/routes/match.py` — uncomment `enqueue_fighter()`
- **Modify** `services/match_scheduler.py` — dispatch `execute_match` + create on-chain pool

### Task 5.2 — Elo-proximity match queue
- **Modify** `packages/backend/src/rawl/services/match_queue.py`
- Replace in-memory dict with Redis sorted sets (score = Elo)
- `ZRANGEBYSCORE` for proximity matching within ±200 Elo, widening by 50 per scheduler tick
- Self-matching prohibition (different `owner_id`)

### Task 5.3 — Missing gateway endpoints
- **Modify** `gateway/routes/match.py` — add `POST /match` (custom match creation)
- **Modify** `gateway/schemas.py` — add `CreateCustomMatchRequest`

### Task 5.4 — Submission rate limiting
- **Modify** `gateway/routes/submit.py` — Redis counter 3/wallet/hour, HTTP 429 + Retry-After

---

## Phase 6: Monitoring & Ops

**Goal:** Expose metrics, expand health checks, operational endpoints.

### Task 6.1 — Prometheus /metrics endpoint
- **Modify** `packages/backend/src/rawl/api/routes/internal.py` — add `/metrics` using `prometheus_client.generate_latest()`

### Task 6.2 — Expand health checks
- **Modify** `packages/backend/src/rawl/monitoring/health_checks.py` — add: Solana RPC, stable-retro ROM check, Celery workers, oracle keypair, model storage (5 missing of 8)

### Task 6.3 — Failed upload retry beat task
- **Modify** `packages/backend/src/rawl/celery_app.py` — add `retry-failed-uploads` every 300s

---

## Phase 7: Frontend Application

**Goal:** Build all spectator-facing pages with Solana wallet integration.

### Task 7.1 — Wallet provider & layout
- **Create** `packages/frontend/src/providers/WalletProvider.tsx` — Solana wallet adapter (Phantom, Solflare, Backpack)
- **Create** `packages/frontend/src/components/Navbar.tsx` — logo, nav links, wallet connect
- **Modify** `packages/frontend/src/app/layout.tsx` — wrap with provider, add navbar

### Task 7.2 — Arena page (live match viewer)
- **Create** `packages/frontend/src/app/arena/[matchId]/page.tsx`
- **Create** `packages/frontend/src/components/MatchViewer.tsx` — canvas JPEG rendering
- **Create** `packages/frontend/src/components/DataOverlay.tsx` — 16 data fields display
- **Create** `packages/frontend/src/components/BettingPanel.tsx` — place bet via wallet adapter
- Uses existing `useMatchVideoStream` + `useMatchDataStream` hooks

### Task 7.3 — Lobby page
- **Create** `packages/frontend/src/app/lobby/page.tsx` — tabs (Upcoming/Live/Completed), game filter
- **Create** `packages/frontend/src/components/MatchCard.tsx` — compact match display
- Uses existing `getMatches()` API client

### Task 7.4 — Leaderboard page
- **Create** `packages/frontend/src/app/leaderboard/page.tsx` — game tabs, ranked table, division badges

### Task 7.5 — Fighter profile page
- **Create** `packages/frontend/src/app/fighters/[fighterId]/page.tsx` — stats, match history

### Task 7.6 — Dashboard page
- **Create** `packages/frontend/src/app/dashboard/page.tsx` — my fighters, training, bets (wallet required)
- **Create** `packages/frontend/src/stores/walletStore.ts` — wallet Zustand store
- **Create** `packages/frontend/src/lib/gateway.ts` — authenticated gateway API client

### Task 7.7 — Update shared types
- **Modify** `packages/frontend/src/types/index.ts` — add TrainingJob, BetInfo
- **Modify** `packages/frontend/src/types/fighter.ts` — add `division_tier`

---

## Phase 8: Contract Enhancements

**Goal:** Add missing contract fields and anti-manipulation analysis.

### Task 8.1 — Contract field additions
- **Modify** `contracts/.../state/match_pool.rs` — add `minimum_bet_amount: u64`, `betting_window_duration: i64`
- **Modify** `contracts/.../constants.rs` — add `MIN_BET_LAMPORTS = 10_000_000`, `DEFAULT_BETTING_WINDOW = 300`
- **Modify** `contracts/.../instructions/place_bet.rs` — add min bet + window checks
- **Modify** `contracts/.../errors.rs` — add `BetBelowMinimum`, `BettingWindowClosed`

### Task 8.2 — Cross-wallet funding analysis
- **Modify** `packages/backend/src/rawl/services/anti_manipulation.py` — implement `flag_cross_wallet_funding()` using Solana tx history

### Task 8.3 — Contract test suite
- **Modify** `packages/contracts/tests/rawl.ts` — comprehensive Anchor tests for all 14 instructions + new fields

---

## File Summary

### New files (24)
| File | Purpose |
|------|---------|
| `backend/.../solana/pda.py` | PDA derivation |
| `backend/.../solana/deserialize.py` | Account deserialization |
| `backend/.../solana/instructions.py` | Instruction builders (14) |
| `backend/.../engine/model_loader.py` | SB3 model loading from S3 |
| `backend/.../engine/failed_upload_handler.py` | S3 dead-letter + retry |
| `backend/.../engine/tasks.py` | Match execution Celery task |
| `backend/.../training/self_play.py` | Self-play callback |
| `backend/alembic/.../002_add_missing_fields.py` | Migration |
| `backend/tests/test_solana/test_pda.py` | PDA tests |
| `backend/tests/test_solana/test_deserialize.py` | Deserialization tests |
| `backend/tests/test_solana/__init__.py` | Test init |
| `frontend/.../providers/WalletProvider.tsx` | Solana wallet provider |
| `frontend/.../components/Navbar.tsx` | Navigation |
| `frontend/.../components/MatchViewer.tsx` | Video canvas |
| `frontend/.../components/DataOverlay.tsx` | Data display |
| `frontend/.../components/BettingPanel.tsx` | Betting UI |
| `frontend/.../components/MatchCard.tsx` | Lobby card |
| `frontend/.../app/arena/[matchId]/page.tsx` | Arena page |
| `frontend/.../app/lobby/page.tsx` | Lobby page |
| `frontend/.../app/leaderboard/page.tsx` | Leaderboard page |
| `frontend/.../app/fighters/[fighterId]/page.tsx` | Fighter profile |
| `frontend/.../app/dashboard/page.tsx` | Dashboard |
| `frontend/.../stores/walletStore.ts` | Wallet store |
| `frontend/.../lib/gateway.ts` | Gateway API client |

### Files to modify (30)
| File | Changes |
|------|---------|
| `db/models/bet.py` | Add `claimed_at` |
| `db/models/fighter.py` | Add `division_tier` |
| `db/models/training_job.py` | Add `tier`, `gpu_type`, `queue_position` |
| `config.py` | Training tier, stable-retro, Solana config |
| `solana/client.py` | Full AsyncClient implementation |
| `solana/account_listener.py` | Real WebSocket subscription |
| `engine/oracle_client.py` | Real Solana tx submission |
| `engine/emulation/retro_engine.py` | RetroEngine (stable-retro wrapper) |
| `engine/match_runner.py` | Uncomment game loop |
| `training/validation.py` | Implement 4 validation steps |
| `training/worker.py` | Gutted — training is off-platform |
| `services/match_queue.py` | Redis sorted set + Elo proximity |
| `services/match_scheduler.py` | Wire match execution dispatch |
| `services/anti_manipulation.py` | Cross-wallet funding |
| `gateway/routes/training.py` | Uncomment Celery, add stop endpoint |
| `gateway/routes/submit.py` | Uncomment Celery, add rate limiting |
| `gateway/routes/match.py` | Uncomment queue, add custom match |
| `gateway/schemas.py` | Add CreateCustomMatchRequest |
| `monitoring/health_checks.py` | Add 5 missing health checks |
| `api/routes/internal.py` | Add /metrics endpoint |
| `main.py` | Register training WS, Solana client, listener |
| `celery_app.py` | Add failed upload retry beat task |
| `frontend/app/layout.tsx` | WalletProvider, Navbar |
| `frontend/types/index.ts` | Add new types |
| `frontend/types/fighter.ts` | Add division_tier |
| `contracts/.../state/match_pool.rs` | Add min bet, window fields |
| `contracts/.../constants.rs` | Add MIN_BET, DEFAULT_BETTING_WINDOW |
| `contracts/.../instructions/place_bet.rs` | Add min bet + window checks |
| `contracts/.../errors.rs` | Add 2 error variants |
| `contracts/tests/rawl.ts` | Comprehensive test suite |

## Verification Strategy

Each phase has its own verification step:
- **Phase 0**: `alembic upgrade head` + `pytest`
- **Phase 1**: `pytest tests/test_solana/`
- **Phase 2**: Oracle txs against `solana-test-validator`
- **Phase 3**: Full match execution for sf2ce with RetroEngine locally
- **Phase 4**: Submit model → validation → training job with progress
- **Phase 5**: Queue fighters → auto-match → execution pipeline end-to-end
- **Phase 6**: `curl /api/metrics` returns Prometheus format, `/api/health` shows all 8 checks
- **Phase 7**: Navigate all pages, connect wallet, place bet
- **Phase 8**: `anchor test` with min bet + window enforcement
