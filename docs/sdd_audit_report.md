# Rawl SDD Compliance Audit Report

**Date:** 2026-02-15
**SDD Version:** v2.6.0 (`Rawl_SDD.md`)
**Audited By:** Automated codebase analysis (6 parallel agents)

---

## Executive Summary

The Rawl platform codebase is approximately **40–50% implemented** against the SDD specification. Strong foundations exist across database models, authentication, Elo rating, game adapters, and Solana contract instructions. However, critical runtime paths — the match engine game loop, Solana backend integration, training pipeline, and the entire frontend — remain scaffolded or missing entirely.

---

## Overall Completion by Subsystem

| Subsystem | Completion | Status |
|-----------|-----------|--------|
| Solana Contracts | ~85% | Most complete — 14 instructions implemented |
| Game Adapters | ~75% | 3 of 5 games fully implemented |
| API / Public Routes | ~70% | Pagination, odds, leaderboard working |
| WebSocket Streaming | ~70% | Video + data channels implemented |
| Gateway / Auth | ~55% | Auth working, route logic mostly scaffolded |
| Match Engine | ~30% | Game loop entirely commented out |
| Monitoring/Observability | ~30% | Metrics defined but not exposed |
| Training Pipeline | ~20% | Celery scaffold only |
| Frontend Pages | ~15% | Only hooks/stores/types — no pages |
| Solana Backend Integration | ~10% | Client, listener, oracle all stubs |

---

## 1. Solana Contracts (~85%)

**Location:** `packages/contracts/programs/rawl/src/`

### Fully Implemented
- **14 instruction dispatch** in `lib.rs`: initialize, create_match, place_bet, lock_match, resolve_match, claim_payout, cancel_match, timeout_match, refund_bet, close_bet, close_match, withdraw_fees, sweep_unclaimed, sweep_cancelled, update_authority
- **3 state accounts**: MatchPool (18 fields), Bet (6 fields), PlatformConfig (7 fields)
- **Constants**: All PDA seeds, DEFAULT_FEE_BPS=300, DEFAULT_TIMEOUT=1800, CLAIM_WINDOW=30 days, MAX_FEE_BPS=1000
- **Error codes**: 18 error codes, all used in instruction validation
- **Parimutuel math**: Basis-point fee calculation, payout computation
- **v2.0 additions**: side_a/b_bet_count, winning_bet_count, cancel_timestamp on MatchPool

### Gaps
- **Missing `MIN_BET` constant** in `constants.rs` (SDD specifies 0.01 SOL / 10,000,000 lamports)
- **Missing MatchPool fields**: `minimum_bet_amount`, `betting_window_duration`, `match_format`, `creator_deposit`
- **No SPL token support** (SDD roadmap v2 mentions this)

---

## 2. Game Adapters (~75%)

**Location:** `packages/backend/src/rawl/game_adapters/`

### Fully Implemented
- **Base ABC** (`base.py`): `GameAdapter` with `MatchState`/`TeamMatchState` dataclasses, methods: `extract_state()`, `is_round_over()`, `is_match_over()`, `validate_info()`
- **sfiii3n** (`sfiii3n.py`): MAX_HEALTH=176, standard best-of-N rounds
- **kof98** (`kof98.py`): MAX_HEALTH=103, TEAM_SIZE=3, team elimination (ignores match_format)
- **tektagt** (`tektagt.py`): MAX_HEALTH=170, 2-character tag, best-of-N at match level
- **Registry** (`__init__.py`): `get_adapter()` lookup with `UnknownGameError`

### Gaps
- **umk3** (`umk3.py`): Stub — raises `NotImplementedError`
- **doapp** (`doapp.py`): Stub — raises `NotImplementedError`

---

## 3. API / Public Routes (~70%)

**Location:** `packages/backend/src/rawl/api/routes/`

### Fully Implemented
- **Matches** (`matches.py`): List with cursor-based pagination (base64 `created_at+id`), detail endpoint
- **Fighters** (`fighters.py`): List (ready only, Elo-ordered), detail endpoint
- **Odds** (`odds.py`): Implied odds calculation (`pool_total / side_total`)
- **Leaderboard** (`leaderboard.py`): Division tiers (Diamond/Gold/Silver/Bronze), Elo ranking
- **Internal** (`internal.py`): Health endpoint
- **Middleware** (`middleware.py`): Redis sliding-window rate limiting, internal JWT (HS256, 5-min expiry), CORS

### Gaps
- No replay endpoints (SDD specifies `GET /api/matches/{id}/replay`)
- No match history on fighter detail responses
- Rate limiting configured per-endpoint but no global fallback metrics

---

## 4. WebSocket Streaming (~70%)

**Location:** `packages/backend/src/rawl/ws/`

### Fully Implemented
- **Video channel** (`broadcaster.py`): Binary JPEG frames, 2 connections/IP limit
- **Data channel** (`broadcaster.py`): JSON with 16 fields (health, timer, round, odds, etc.), 5 connections/IP limit
- **Training WebSocket** (`training_ws.py`): Training progress stream

### Gaps
- **`training_ws.py` not registered** in `main.py` — endpoint exists but is unreachable
- No Redis Streams subscription for cross-process frame distribution (direct broadcast only)

---

## 5. Gateway / Auth (~55%)

**Location:** `packages/backend/src/rawl/gateway/`

### Fully Implemented
- **Auth** (`auth.py`): HMAC-SHA256 API key derivation, Ed25519 wallet signature verification (PyNaCl), API key hash storage
- **Wallet registration** (`routes/register.py`): Challenge-response flow, creates User with wallet_address + api_key_hash
- **Leaderboard** (`routes/leaderboard.py`): Division tiers, Elo ranking, convenience mirror of public API
- **Fighter list/detail** (`routes/fighters.py`): Scoped to authenticated wallet
- **Match queue** (`routes/match.py`): `POST /queue` validates ownership + status
- **Schemas** (`schemas.py`): Pydantic models for all request/response types

### Partially Implemented
- **Training routes** (`routes/training.py`): `POST /train` and `GET /train/{job_id}` exist but Celery dispatch commented out; GET lacks owner authorization check
- **Submit route** (`routes/submit.py`): Creates fighter + triggers validation (both commented out); conflates fighter creation with model submission
- **Fighters recalibrate** (`routes/fighters.py`): Status validation works, Celery task commented out

### Missing
- **`POST /api/gateway/match`** — Create custom match (pick opponent, set betting params) not implemented
- **`POST /api/gateway/train/{job_id}/stop`** — Stop training job not implemented
- **`WS /ws/gateway/train/{job_id}`** — WebSocket training subscription not implemented
- **Semantic mismatch**: `/register` registers wallets instead of fighters (SDD says it should register fighters)
- **Rate limiting on `/submit`**: SDD requires 3/wallet/hour, 1 concurrent validation — not enforced
- **Training tiers**: No Free/Standard/Pro tier parameter in `TrainRequest`

---

## 6. Match Engine (~30%)

**Location:** `packages/backend/src/rawl/engine/`

### Fully Implemented
- **Match result** (`match_result.py`): Canonical JSON hash with `hash_version=2`, 4-step tiebreaker (health diff → rounds won → last-round health → SHA-256 coin flip)
- **Frame processor** (`frame_processor.py`): RGB → grayscale 128x128, MJPEG JPEG encoding
- **Replay recorder** (`replay_recorder.py`): MJPEG recording, JSON sidecar at 10Hz, u64 LE frame index, S3 upload
- **Field validator** (`field_validator.py`): CONSECUTIVE_THRESHOLD=300, TOTAL_THRESHOLD=900, per-field counters with warnings

### Scaffold Only (Commented Out)
- **Match runner** (`match_runner.py`): Lines 79–220 entirely commented out
  - Entry logging and adapter init work
  - Game loop (DIAMBRA step, observation processing, action inference, frame broadcast) is all comments
  - Oracle calls are placeholder (`await oracle_client.submit_lock/resolve/cancel`)
- **DIAMBRA manager** (`diambra_manager.py`): `start()` raises `NotImplementedError`; `get_env_settings()` returns correct config dict
- **Oracle client** (`oracle_client.py`): All 3 transaction methods raise `NotImplementedError`; correct method signatures exist

---

## 7. Monitoring / Observability (~30%)

**Location:** `packages/backend/src/rawl/monitoring/`

### Fully Implemented
- **Logging** (`logging_config.py`): structlog with JSON output, trace ID generation (16-char hex)
- **Health checks** (`health_checks.py`): DB, Redis, S3 connectivity with latency tracking
- **Health checker** (`services/health_checker.py`): Match Runner heartbeat (15s Celery Beat, 60s timeout, auto-cancel)

### Partially Implemented
- **Metrics** (`metrics.py`): Prometheus Counter/Gauge/Histogram objects defined for matches, inference, WS, API, training, S3, Solana — **but not exposed via `/metrics` endpoint**
- **Trace ID**: Generated but not auto-injected into request context

### Missing
- **`/metrics` endpoint** not mounted in FastAPI app
- **Prometheus scrape config** not present
- **Alerting**: No PagerDuty/OpsGenie integration, no severity routing
- **Grafana dashboards**: 4 dashboards specified in SDD (Platform Overview, Match Operations, Training Pipeline, Financial Operations) — none exist
- **7 of 8 health checks missing**: Oracle keypair (5min), DIAMBRA gRPC (30s), Solana RPC (30s), Celery workers (60s), Redis Streams lag (15s), WebSocket health (15s), Account Listener (15s)
- **Incident runbooks**: 4 required P1 runbooks not documented
- **On-call rotation**: No scheduling, SLA tracking, or escalation paths

---

## 8. Training Pipeline (~20%)

**Location:** `packages/backend/src/rawl/training/`

### Fully Implemented
- **DB models**: TrainingJob (status lifecycle, timesteps, reward), CalibrationMatch (attempt tracking)
- **Elo service** (`services/elo.py`): Adaptive K-factors (40/20/16), calibration (5 reference Elos, min 3/5 success, max 2 retries), seasonal reset, division assignment
- **Celery framework** (`celery_app.py`): Redis broker/backend, Beat scheduler, autodiscovery
- **PPO config** (`pipeline.py`): `create_ppo_config()` with hardcoded hyperparameters

### Scaffold Only
- **Worker task** (`worker.py`): Celery task decorated, DB session management works, DIAMBRA/PPO code commented out
- **Validation pipeline** (`validation.py`): 4-step structure defined with thresholds (5ms p99, 60s sandbox, 100 test frames) — all 4 steps are comments

### Missing
- **Training tiers**: No Free/Standard/Pro separation, no GPU allocation logic, no per-wallet job limits
- **Self-play training loop**: No opponent pool, no 70/30 sampling, no checkpoint versioning
- **Progress streaming**: No Redis metrics publication (every 10K steps), no WebSocket subscription
- **Agent Registry**: Only `get_fighter_model_path()` and `update_fighter_status()` — no versioning, no Elo-per-checkpoint

---

## 9. Frontend (~15%)

**Location:** `packages/frontend/src/`

### Implemented (Infrastructure Only)
- **Hooks**: `useMatchDataStream`, `useMatchVideoStream` (WebSocket consumers)
- **Store**: Zustand `matchStore` for state management
- **API client**: `lib/api.ts` with functions for public endpoints
- **Types**: TypeScript interfaces for Match, Fighter, Bet, etc.
- **Components**: `HealthBar.tsx` (color-graded health bar)
- **Layout**: Minimal `layout.tsx` with Rawl metadata

### Completely Missing (0 Pages)
- **Arena View**: Match viewing with live video + betting
- **Lobby View**: Browse upcoming/live matches
- **Leaderboard View**: Rankings by game/division
- **Fighter Profile View**: Stats, match history, Elo graph
- **User Dashboard**: My fighters, training jobs, bet history
- **Wallet integration**: Solana wallet adapter (Phantom, Solflare)
- **Betting UI**: Place bets, claim payouts
- **Training UI**: Start/monitor training jobs
- **Responsive design**: No mobile layout

---

## 10. Solana Backend Integration (~10%)

**Location:** `packages/backend/src/rawl/solana/`

### Scaffold Only
- **Client** (`client.py`): 100% stub — `AsyncClient` commented out, `get_health()` hardcoded to `True`
- **Account Listener** (`account_listener.py`): WebSocket subscription commented out, `_handle_message()` and `_catch_up()` empty, sleeps in a loop
- **Oracle** (`oracle.py`): Keypair file format validation only (checks 64-byte array), no actual signing test

### Missing
- **RPC calls**: No `get_account_info`, `send_transaction`, `confirm_transaction`
- **Transaction building**: No instruction serialization for any of the 14 contract instructions
- **PDA derivation**: No backend PDA computation (exists only in Anchor program)
- **Event parsing**: Account listener has no deserialization for MatchPool/Bet state changes
- **Keypair security**: File-based JSON storage (SDD requires HSM v1, multi-sig v2)

---

## 11. Database Models

**Location:** `packages/backend/src/rawl/db/models/`

| Model | Status | Missing Fields |
|-------|--------|---------------|
| `user.py` | Complete | — |
| `match.py` | Complete | 20+ fields including PG-only states (`pending_resolution`, `resolution_failed`) |
| `bet.py` | Complete | Missing `claimed_at` timestamp |
| `fighter.py` | Complete | Missing `division_tier` column |
| `training_job.py` | Partial | Missing `tier`, `gpu_type`, `queue_position` |
| `calibration_match.py` | Complete | — |
| `failed_upload.py` | Complete | Not actually used by match_runner (logic commented out) |

**Migration**: Single `001_initial.py` creates all 7 tables. No migration history beyond initial schema.

---

## 12. Services

**Location:** `packages/backend/src/rawl/services/`

| Service | Status | Notes |
|---------|--------|-------|
| `elo.py` | Fully Implemented | K-factors, calibration, seasonal reset, divisions |
| `match_queue.py` | Partial | In-memory queue, pairs any two fighters (no Elo proximity) |
| `match_scheduler.py` | Implemented | Celery Beat task iterating queues |
| `anti_manipulation.py` | Implemented | Betting concentration (>50% + >10 SOL), win-rate audit (>80% on 10+ bets) |
| `health_checker.py` | Implemented | 15s heartbeat, 60s timeout, auto-cancel |
| `agent_registry.py` | Partial | Model path lookup + status update only, no versioning |

---

## 13. Infrastructure

**Location:** `docker-compose.yml`, `infra/k8s/`

### Docker Compose (Local Dev)
- PostgreSQL 16, Redis 7, MinIO — **3 of ~8 needed services**
- Missing: DIAMBRA, Celery worker, Solana test validator, account listener, frontend

### Kubernetes
| Manifest | Status | Gaps |
|----------|--------|------|
| `backend-deployment.yaml` | 2 replicas, readiness probe | No HPA, no resource tuning |
| `worker-deployment.yaml` | 2 replicas, `nvidia.com/gpu: 1` | No T4/A10G node selectors, no priority scheduling |
| `account-listener-deployment.yaml` | 1 replica, lightweight | No health check for WS connection |

### Missing Infra
- No Terraform/CloudFormation for GPU VMs (SDD: 8 T4 + 4 A10G)
- No HorizontalPodAutoscaler manifests
- No frontend deployment config (Vercel/Cloudflare Pages)
- No Solana RPC config (Helius/QuickNode)
- No Grafana/Prometheus K8s manifests

---

## Critical Gaps Summary

### Launch Blockers (Must Fix)

| # | Gap | Location | Impact |
|---|-----|----------|--------|
| 1 | Match engine game loop commented out | `engine/match_runner.py:79-220` | No matches can run |
| 2 | Solana client is 100% stub | `solana/client.py` | No on-chain interaction |
| 3 | Oracle client raises NotImplementedError | `engine/oracle_client.py` | No match locking/resolving |
| 4 | Account listener is empty | `solana/account_listener.py` | No on-chain event detection |
| 5 | DIAMBRA manager raises NotImplementedError | `engine/diambra_manager.py` | No game environment |
| 6 | Training validation all commented | `training/validation.py` | Models can't be validated |

### High Priority

| # | Gap | Location | Impact |
|---|-----|----------|--------|
| 7 | Zero frontend pages | `packages/frontend/src/app/` | No user-facing product |
| 8 | Match queue has no Elo proximity | `services/match_queue.py` | Unfair matchmaking |
| 9 | Training Celery dispatch commented out | `gateway/routes/training.py` | Training jobs don't start |
| 10 | Prometheus metrics not exposed | `monitoring/metrics.py` | No observability |
| 11 | Contract missing MIN_BET + match fields | `contracts/.../constants.rs` | Incomplete wagering params |
| 12 | DB models missing fields | `db/models/bet.py`, `fighter.py` | Schema incomplete |

---

## Estimated Path to Production

| Phase | Focus | Estimated Duration |
|-------|-------|-------------------|
| **Phase 1** | Core engine: match loop, DIAMBRA, oracle | 4–5 weeks |
| **Phase 2** | Solana integration: client, listener, oracle txs | 3–4 weeks |
| **Phase 3** | Training pipeline: validation, PPO, GPU tiers | 3–4 weeks |
| **Phase 4** | Frontend: Arena, Lobby, Dashboard, wallet | 4–5 weeks |
| **Phase 5** | Gateway routes + missing DB fields | 2–3 weeks |
| **Phase 6** | Monitoring, infra, testing, hardening | 3–4 weeks |
| **Total** | | **~20–25 weeks** |

---

## What's Solid (SDD-Compliant)

These components are production-quality and closely match the SDD specification:

- **Elo service**: Adaptive K-factors, calibration flow, seasonal reset, 4-step tiebreaker
- **Replay recorder**: MJPEG + JSON sidecar + u64 LE byte-offset index for O(1) seek
- **Frame processor**: RGB → grayscale 128x128, JPEG encoding
- **Field validator**: Consecutive/total threshold detection with one-time warnings
- **Match result hashing**: Canonical JSON (sorted keys, no whitespace) → SHA-256 with `hash_version`
- **Authentication**: HMAC-SHA256 API key derivation, Ed25519 wallet signature verification
- **Anti-manipulation**: Betting concentration detection, win-rate pattern audit
- **Health checker**: Heartbeat monitoring with auto-cancel on timeout
- **Rate limiting**: Redis sliding-window counters per endpoint
- **Internal JWT**: HS256 with 5-min expiry for SSR
- **Game adapters**: sfiii3n, kof98, tektagt fully implement the adapter interface
- **Solana contracts**: 14 instructions with proper PDA derivation, parimutuel math, rent reclamation
- **Database schema**: 7 tables with proper indexes, constraints, and timezone-aware timestamps
- **Cursor pagination**: Base64-encoded `(created_at, id)` tuples across all list endpoints
