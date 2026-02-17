# Rawl Platform — Launch Roadmap

> Phased guide to go from codebase to production.

---

## Phase 1: Local Dev Environment Setup ✅ COMPLETE

Get everything running on your machine.

### Prerequisites

| Tool | Required | Notes |
|------|----------|-------|
| Docker Desktop | 28.x+ | Must be running before `docker compose up` |
| Python | 3.11+ | 3.12 tested and working |
| Node.js | 18+ | v22 tested and working |
| WSL2 + Ubuntu | Required | Solana test validator does NOT work on Windows natively |
| Rust/Cargo | For Anchor | Needed for Anchor CLI installation |

### Step-by-step

1. **Stop local PostgreSQL** — If you have a local PostgreSQL service, it conflicts with Docker on port 5432
   ```bash
   # Find service name
   sc query type= service state= all | grep -i postgres
   # Stop it (requires admin)
   net stop postgresql-x64-18   # adjust version number
   ```

2. **Start Docker Desktop** — Must be running before docker compose
   ```bash
   # Launch Docker Desktop, then verify:
   docker info
   ```

3. **Docker services** — Start PostgreSQL, Redis, MinIO
   ```bash
   cd /c/Projects/Rawl
   docker compose up -d
   # Wait for healthy:
   docker compose ps
   ```

4. **Environment** — Copy and configure secrets
   ```bash
   cp .env.example .env
   # Defaults work for local dev — no changes needed
   ```

5. **Backend dependencies** — Install Python packages
   ```bash
   cd packages/backend
   pip install -e ".[dev]"
   pip install stable-retro opencv-python-headless
   ```

6. **Database** — Run migrations
   ```bash
   cd packages/backend
   python -m alembic upgrade head
   ```

7. **MinIO buckets** — Create S3 buckets for replays and models
   ```bash
   docker exec rawl-minio-1 sh -c 'mc alias set local http://localhost:9000 minioadmin minioadmin && mc mb local/rawl-replays --ignore-existing && mc mb local/rawl-models --ignore-existing'
   ```

8. **Backend** — Start FastAPI dev server (port 8080, NOT 8000)
   ```bash
   cd packages/backend
   uvicorn rawl.main:create_app --factory --reload --host 0.0.0.0 --port 8080
   ```
   > **Port 8080**: The Solana test validator uses port 8000 for gossip, so the backend must use a different port.

9. **Frontend** — Install deps and start Next.js
   ```bash
   cd packages/frontend
   npm install
   npm run dev
   ```

10. **Solana test validator** — Must run inside WSL2 (crashes on Windows)
    ```bash
    wsl -d Ubuntu-22.04 -- bash -c '
      export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
      rm -rf /tmp/rawl-test-ledger
      solana-test-validator --reset --ledger /tmp/rawl-test-ledger
    '
    ```
    > First-time setup: install Solana CLI inside WSL:
    > ```bash
    > wsl -d Ubuntu-22.04 -- bash -c 'curl -sSfL https://release.anza.xyz/stable/install | sh'
    > ```

11. **Celery workers** — Start worker and beat scheduler (in separate terminals)
    ```bash
    cd packages/backend
    celery -A rawl.celery_app worker --loglevel=info --pool=solo
    ```
    ```bash
    cd packages/backend
    celery -A rawl.celery_app beat --loglevel=info
    ```

12. **Emulation (stable-retro)** — Install in WSL2 and import SF2 Genesis ROM
    ```bash
    # Install stable-retro in WSL2 (does NOT work on native Windows)
    wsl -d Ubuntu-22.04 -- pip3 install stable-retro Pillow

    # Copy ROM to stable-retro data directory
    # Source: "Street Fighter II' - Special Champion Edition (U) [!].bin"
    wsl -d Ubuntu-22.04 -- cp "/mnt/c/Projects/Rawl/roms/rom.bin" \
      /usr/local/lib/python3.10/dist-packages/stable_retro/data/stable/StreetFighterIISpecialChampionEdition-Genesis-v0/rom.md

    # Verify
    wsl -d Ubuntu-22.04 -- python3 scripts/test_stable_retro.py
    ```
    > ROM SHA1: `a5aad1d108046d9388e33247610dafb4c6516e0b`
    > Game ID: `StreetFighterIISpecialChampionEdition-Genesis-v0`
    > No BIOS files needed. Genesis core is bundled with stable-retro.

### Health Check Verification

After all services are running, verify:
```bash
curl -s http://localhost:8080/api/health | python -m json.tool
```

All 8 components should report healthy:

| Component | Port/URL | Notes |
|-----------|----------|-------|
| PostgreSQL | Docker `localhost:5432` | Via docker compose |
| Redis | Docker `localhost:6379` | Via docker compose |
| MinIO (S3) | Docker `localhost:9000` | Console at `:9001` |
| Backend | `localhost:8080` | FastAPI + uvicorn |
| Frontend | `localhost:3000` | Next.js dev server |
| Celery | Redis broker | Worker + Beat |
| Solana RPC | WSL `localhost:8899` | Test validator |
| Retro | WSL2 in-process | stable-retro + genesis_plus_gx core |

### Bugs Fixed During Phase 1

These issues were found and fixed during initial setup:

- **`next.config.ts` → `next.config.mjs`** — Next.js 14 doesn't support `.ts` config files
- **Redis health check** — `RedisPool` was missing `ping()` and `scan()` delegation methods
- **Solana health check** — `AsyncClient` has `is_connected()` not `get_health()`
- **Celery task discovery** — `autodiscover_tasks` only finds `tasks.py`; added `celery.conf.include` for modules with other names (`match_scheduler.py`, `health_checker.py`, `worker.py`, `validation.py`)
- **Port conflict** — Solana gossip uses port 8000; backend moved to port 8080
- **Frontend API URLs** — Updated hardcoded `localhost:8000` → `localhost:8080` in `api.ts`, `gateway.ts`, `useMatchStream.ts`

### Phase 1 Checklist
- [x] Local PostgreSQL service stopped (port 5432 freed)
- [x] Docker services healthy (`docker compose ps` — all 3 green)
- [x] Database migrated (2 Alembic migrations applied)
- [x] MinIO buckets created (`rawl-replays`, `rawl-models`)
- [x] `.env` configured
- [x] Backend responds at `http://localhost:8080/api/health`
- [x] Frontend loads at `http://localhost:3000`
- [x] Solana test validator running in WSL2 (`localhost:8899`)
- [x] Celery worker running (6 tasks registered)
- [x] Celery beat running (3 scheduled tasks)
- [x] DIAMBRA replaced with stable-retro (genesis_plus_gx / SF2 Genesis)
- [x] ROM imported for stable-retro (SF2 Special Champion Edition, Genesis)
- [x] Emulation verified: 120 frames, health/round state reads correctly
- [ ] Database seeded (`python scripts/seed-db.py` — not yet run)

---

## Phase 2: Integration Testing & Bug Fixing

Verify the pieces actually work together. This is likely the longest phase.

### 2.1 Deploy Contracts to Local Validator ✅ COMPLETE

Anchor 0.30.1 installed in WSL2 via `cargo install` with Rust 1.88.0.

**Build** (must use platform-tools v1.52 due to `constant_time_eq` crate compatibility):
```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.cargo/bin:$HOME/.local/share/solana/install/active_release/bin:$PATH"
  cd /mnt/c/Projects/Rawl/packages/contracts
  # Install v1.52 tools first
  cargo-build-sbf --install-only --tools-version v1.52 --force-tools-install
  # Build with v1.52
  cargo-build-sbf --tools-version v1.52 --manifest-path programs/rawl/Cargo.toml --sbf-out-dir target/deploy
'
```

**Deploy** (requires WSL wallet with SOL):
```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana program deploy /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl.so \
    --program-id /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl-keypair.json
'
```

**Initialize PlatformConfig** (run after deployment):
```bash
cd /c/Projects/Rawl
# Fund oracle wallet first:
wsl -d Ubuntu-22.04 -- bash -c 'export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH" && solana airdrop 100 AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4'
# Then initialize:
python scripts/init-platform.py
```

| Item | Value |
|------|-------|
| Program ID | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` |
| Oracle | `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4` |
| PlatformConfig PDA | `CvKx2cxZBYwUUqjFE73s5KggNntgQth5yAWhSLDuPTUj` |
| Fee | 300 BPS (3%) |
| Match Timeout | 1800s (30 min) |

### 2.2 Seed the Database ✅ COMPLETE

```bash
cd /c/Projects/Rawl && python scripts/seed-db.py
```

Seeds 3 users with API keys, 9 fighters (3 games x 3 users), 3 matches. Outputs API keys for gateway testing.

### 2.3 Emulation Engine Migration ✅ COMPLETE

DIAMBRA replaced with stable-retro. Game changed from SF3 Dreamcast (unverified) to **SF2 Special Champion Edition (Genesis)** (verified working 2026-02-16).

**What changed:**
- `config.py` — DIAMBRA settings replaced with `retro_game`, `retro_integration_path`, `retro_obs_size`
- `match_runner.py` — Imports `RetroEngine` instead of `DiambraManager`
- `training/worker.py` — Gutted; training is off-platform now (`NotImplementedError`)
- `health_checks.py` — `check_retro()` replaces `check_diambra()`
- `game_adapters/base.py` — Docstrings updated (DIAMBRA → emulation engine)

**New files:**
- `engine/emulation/base.py` — `EmulationEngine` ABC
- `engine/emulation/retro_engine.py` — RetroEngine wrapping stable-retro

**Deleted:**
- `engine/diambra_manager.py`

**Emulation verified (2026-02-16):**
- stable-retro 0.9.9 installed in WSL2 (Ubuntu-22.04)
- Genesis core (`genesis_plus_gx_libretro.so`) bundled with stable-retro
- ROM: `Street Fighter II' - Special Champion Edition (U) [!].bin` (SHA1: `a5aad1d108046d9388e33247610dafb4c6516e0b`)
- All 6 RAM variables built-in (health, enemy_health, matches_won, enemy_matches_won, continuetimer, score)
- No BIOS required, no custom data.json needed, no RAM address discovery needed
- 2-player mode works with `Actions.FILTERED` → `MultiBinary(24)`
- Frame output: 200x256x3 RGB

### 2.4 Match Execution End-to-End ✅ COMPLETE

**Gateway & scheduling:**
- [x] Gateway auth via API key (X-Api-Key header)
- [x] Queue fighters via `POST /api/gateway/queue`
- [x] Match scheduler pairs fighters by Elo proximity
- [x] Match record created in DB
- [x] `execute_match.delay()` dispatched to Celery
- [x] WebSocket data channel connects and streams
- [x] RetroEngine replaces DiambraManager in match_runner

**Emulation (SF2 Genesis verified):**
- [x] stable-retro loads SF2 Genesis ROM and runs 2-player games
- [x] All RAM variables available (no address discovery needed)
- [x] Built-in 2P save state (Champion.Level1.RyuVsGuile)
- [x] Fix sfiii3n adapter MAX_HEALTH (176→160)
- [x] Create sf2ce game adapter (MAX_HEALTH=176, delta-based round detection)
- [x] Update RetroEngine info translation for SF2 key names (health/enemy_health + backward-compat p1_/p2_ prefix)
- [x] Update config.py retro_game to SF2 Genesis
- [x] Update health check to use `import stable_retro`
- [x] WSL2 E2E smoke test: full bo3 match completes (2538 FPS, delta round detection verified)

**Inference pipeline & models:**
- [x] Inference pipeline aligned (84x84x4 grayscale, CnnPolicy, 4-frame stacking)
- [x] Match runner frame stacking buffer (deque-based, matches training VecFrameStack)
- [x] Trained SF2 models available (PPO, 200K–2M step checkpoints)
- [x] Pretrained community models imported (linyiLYi, thuongmhh)
- [x] Multi-model support (auto-detect Rawl/thuongmhh/linyiLYi from obs/action spaces)
- [x] Training script with tuned asymmetric reward (3x attack, exponential round bonuses)

### 2.5 Betting Flow ✅ VERIFIED

Full betting lifecycle tested end-to-end on local Solana (`scripts/test-betting-flow.py`):
- Create match pool on-chain (MatchPool + Vault PDAs)
- Place bets from two wallets (1 SOL + 0.5 SOL)
- Lock match (oracle-only)
- Resolve match with winner (oracle-only)
- Claim payout (winner receives net pool after 3% fee)
- Platform fee remains in vault for treasury withdrawal

**Backend endpoints:**
- `GET /api/bets?wallet=X` — Query user bets
- `POST /api/matches/{id}/bets` — Record bet after on-chain tx

**Frontend hooks:**
- `usePlaceBet()` — Build + sign + send `place_bet` instruction
- `useClaimPayout()` — Build + sign + send `claim_payout` instruction
- `useRefundBet()` — Build + sign + send `refund_bet` instruction

### 2.6 Training Pipeline → Off-Platform

Training has been moved off-platform. Users rent their own GPUs and run an open-source training package, then submit checkpoints via `POST /api/gateway/submit`.

**Platform responsibilities:**
- Publish pip-installable training package (stable-retro env wrapper, observation preprocessing, default PPO config, macro action support)
- Validate submitted checkpoints in a sandboxed container (load test, action space check, latency check)
- Quality control via Elo system — bad models lose, Elo tanks, nobody bets on them

**Not platform responsibilities:**
- GPU provisioning, capacity planning, training ops
- Training algorithm choice (PPO, A3C, etc. — user's decision)

### 2.7 Elo & Calibration ✅ COMPLETE

Calibration pipeline fixed end-to-end. 4 bugs resolved:

**Bugs fixed:**

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `training/validation.py` | After validation, set fighter status to `"ready"` — skipping calibration entirely | Set status to `"calibrating"` and dispatch `run_calibration_task.delay()` |
| 2 | `engine/match_runner.py` | `run_match()` unconditionally called oracle, Redis streaming, replay recording, S3 upload — calibration matches have no on-chain pool | Added `calibration: bool = False` param; guards 6 oracle call sites, replay, streaming, heartbeat, S3 upload |
| 3 | Reference models | `run_calibration()` loads models from `reference/{game_id}/{ref_elo}` — these S3 keys didn't exist | Created `scripts/upload_reference_models.py` to upload baseline model at 5 Elo levels |
| 4 | `services/elo.py` | After calibration, `matches_played`, `wins`, `losses` stayed at 0 — K-factor threshold (10 matches) ignored calibration | Track `wins_count` during loop, update `matches_played`, `wins`, `losses` after calibration |

**Status transitions:** `validating → calibrating → ready` (or `calibration_failed`)

**Verification checklist:**
1. [x] Elo math: `calculate_new_rating()` with K-factors 40/20/16 at correct thresholds
2. [x] Division placement: Bronze < 1200, Silver < 1400, Gold < 1600, Diamond >= 1600
3. [x] Seasonal reset: `1200 + 0.5 * (R - 1200)`
4. [x] Calibration: 5 reference matches, min 3/5 success, sequential Elo updates
5. [x] Stats: `matches_played`/`wins`/`losses` updated after calibration
6. [x] Queue protection: `Fighter.status == "ready"` guard prevents calibrating fighters from matchmaking

### 2.8 Frontend ↔ Backend ✅ COMPLETE

All verified working:
- [x] Lobby page loads matches with correct status filters
- [x] Leaderboard renders (client-side data fetch)
- [x] Dashboard renders with wallet gate
- [x] API endpoints return seeded data
- [x] CORS preflight works
- [x] WebSocket connections established

### 2.9 Bugs Fixed During Phase 2

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `engine/tasks.py` | Elo update called with wrong kwargs (`fighter_a_id`/`fighter_b_id`/`winner` vs `winner_id`/`loser_id`) | Determine winner/loser from `result.winner` before calling `update_elo_after_match` |
| 2 | `redis_client.py` | Missing sorted set methods (`pipeline`, `zadd`, `zrange`, `zrangebyscore`, `zrem`, `set`, `delete`) used by match_queue | Added delegation methods to `RedisPool` class |
| 3 | `services/match_scheduler.py` | `match_format="bo3"` (string) instead of integer | Changed to `settings.default_match_format` (int 3) |
| 4 | `gateway/schemas.py` | `CreateCustomMatchRequest.match_format` was string pattern `"bo1|bo3|bo5"` but DB expects int | Changed to `int` with `ge=1, le=5` |
| 5 | `main.py` | `account_listener.stop()` called without `await` | Added `await` |
| 6 | `solana/client.py` | `confirm_transaction` received string instead of `Signature` object | Keep `result.value` as `Signature`, convert to string only for logging/return |
| 7 | `solana/account_listener.py` | `settings.program_id` (string) passed to `get_program_accounts()` which expects `Pubkey` | Added `Pubkey.from_string(settings.program_id)` |
| 8 | `lib.rs` / `Anchor.toml` / `.env` | Invalid placeholder program ID `RawL111...` | Generated real keypair, updated all references |
| 9 | `scripts/seed-db.py` | Users seeded without API keys, gateway auth unusable | Generate API keys via `derive_api_key` and store hashes |
| 10 | `create_match.rs` | Vault PDA created as system-owned; `claim_payout`/`refund` can't debit it | Initialize vault via `create_account` CPI with `owner=program_id` |
| 11 | `instructions.py` | `build_create_match_ix` vault marked `is_writable=False` | Changed to `is_writable=True` (vault now init'd in create_match) |
| 12 | `instructions.py` | `build_place_bet_ix` had unused `vault_bump` param | Removed unused parameter |
| 13 | `frontend/lib/solana.ts` | PDA derivation used string encoding instead of binary UUID bytes | Rewrote `matchIdToBytes()` to parse UUID hex → 16 bytes + 16 zero pad |
| 14 | `frontend/lib/solana.ts` | `placeBetTransaction` was a stub that threw an error | Replaced with PDA derivers + instruction data builders; created `usePlaceBet` hook |
| 15 | `frontend/types/match.ts` | `match_format: string` but backend returns `int` | Changed to `number` |
| 16 | `frontend/arena/page.tsx` | `match_format.toUpperCase()` crashes on number | Changed to `Bo{match.match_format}` |
| 17 | `match_scheduler.py` | No on-chain match creation when `has_pool=True` | Added `_create_onchain_pool()` helper |
| 18 | `account_listener.py` | `_handle_bet_update` returned early if bet record not in DB | Now creates missing bet records from on-chain data |
| 19 | `game_adapters/sfiii3n.py` | `MAX_HEALTH = 176` — incorrect, actual max is 160 | Changed to `MAX_HEALTH = 160` (confirmed by cheat DBs, CPS3 RAM maps, community damage data) |
| 20 | `training/validation.py` | After validation passes, set status to `"ready"` — skipping calibration | Set status to `"calibrating"` + dispatch `run_calibration_task.delay()` |
| 21 | `engine/match_runner.py` | `run_match()` unconditionally calls oracle/Redis/replay/S3 — calibration has no on-chain pool | Added `calibration: bool` param, guards 6 oracle sites + streaming + replay + S3 |
| 22 | Reference models missing | `run_calibration()` loads from `reference/{game_id}/{elo}` — keys don't exist in S3 | Created `scripts/upload_reference_models.py` to seed MinIO |
| 23 | `services/elo.py` | `matches_played`/`wins`/`losses` not updated after calibration — K-factor threshold off by 5 | Track wins during calibration loop, update stats before commit |

### 2.10 Match Viewer & Training Tooling ✅ COMPLETE

Standalone dev tools for running matches and training models locally.

**Scripts:**
- `scripts/watch_match.py` — Pygame live match viewer with sidebar HUD (health bars, round/match scores, timer), input overlay, scrolling input log, pause/step controls
- `scripts/train_sf2_baseline.py` — PPO training with asymmetric reward (3x attack bonus, exponential round bonuses), linear LR/clip schedules, frame skip, WarpFrame preprocessing

**Multi-model auto-detection:**
- `FrameStacker84` — Rawl-trained models (84x84x4 grayscale, MultiBinary actions)
- `FrameStackerLinyiLYi` — linyiLYi pretrained model (84x84x4 grayscale, discrete action via LUT)
- `FrameStackerThuongmhh` — thuongmhh pretrained model (100x128x3 RGB, MultiDiscrete actions)
- Auto-detect model type from observation/action space shape at load time

**Model checkpoints:** stored in `models/` (gitignored), including PPO checkpoints at 200K–2M steps plus pretrained community models.

### 2.11 Match-to-Settlement Integration ✅ COMPLETE

Full pipeline verified end-to-end in WSL2 (2026-02-17). Production `run_match()` executed
against live Docker services (Redis, MinIO, PostgreSQL) and Solana test validator.

- [x] Full pipeline: models loaded → engine.start() → game loop → result → oracle → on-chain resolve
- [x] Match result hashing and S3 upload before settlement
- [x] WebSocket video streaming (MJPEG @ 30fps) during live match
- [x] WebSocket data channel (JSON @ 10Hz) during live match
- [x] Replay recording and S3 archival
- [x] Frontend build passes (fixed `@rawl/shared` import, `match_format` type, `Uint8Array` TS 5.6)
- [x] End-to-end: queue → match → stream → hash → resolve → claim

**Test results:**

| Component | Result | Details |
|-----------|--------|---------|
| Model loading (S3 → PPO) | PASS | 2 models loaded, cache hit verified |
| RetroEngine (SF2 Genesis) | PASS | 256x256x3 obs, info translation OK |
| Game loop (Bo3) | PASS | P2 won 2-0, 7749 frames, 32.7s (~237 fps) |
| Redis video stream | PASS | 500+ msgs, valid JPEG headers (22KB/frame) |
| Redis data stream | PASS | 166 msgs at 10Hz, 8 fields per message |
| Match hash (SHA-256) | PASS | S3 upload + roundtrip download verified identical |
| Replay (mjpeg+json+idx) | PASS | 178.6MB mjpeg, 342KB json, 62KB idx uploaded to S3 |
| Oracle lock (production path) | PASS | `oracle_client.submit_lock()` → on-chain status=Locked |
| Oracle resolve (production path) | PASS | `oracle_client.submit_resolve()` → on-chain status=Resolved, winner=SideB |
| Betting (create→bet→lock→resolve→claim) | PASS | 1.455 SOL payout (1.5 total - 3% fee) |
| Frontend build | PASS | `next build` succeeds, all pages generated |

**Environment:** WSL2 Ubuntu-22.04, Python 3.10.12, stable-retro 0.9.9, Docker services on Windows host (10.255.255.254), Solana validator local in WSL2 (Agave 3.1.7).

**Frontend fixes applied:**
- `tsconfig.json` — Added `@rawl/shared` path alias + include
- `next.config.mjs` — Added `transpilePackages: ['@rawl/shared']`
- `package.json` — Added `"@rawl/shared": "file:../shared"` dependency
- `.eslintrc.json` — Removed missing `@typescript-eslint/no-unused-vars` rule
- `lib/api.ts` — Added `fighter_id` to `getMatches()` query params
- `lib/solana.ts` — Fixed `Uint8Array` TS 5.6 strictness (`crypto.subtle.digest`)
- `components/MatchCard.tsx` — `match_format` is number, not string (`Bo{n}`)

### Phase 2 Checklist
- [x] Contracts deployed to local Solana validator
- [x] PlatformConfig initialized on-chain (oracle, 3% fee, 30min timeout)
- [x] Database seeded with reference data + API keys
- [x] Gateway API auth + matchmaking queue works
- [x] Match scheduler pairs fighters and creates matches
- [x] All frontend pages render with real backend data
- [x] DIAMBRA replaced with stable-retro (RetroEngine implemented)
- [x] Betting → resolve → payout works on local Solana
- [x] Wallet connect + bet submission (frontend hooks + PDA derivation implemented)
- [x] Training pipeline moved off-platform
- [x] SF2 Genesis ROM imported and emulation verified (2026-02-16)
- [x] All RAM variables available (built-in, no discovery needed)
- [x] Built-in 2P save state works (Champion.Level1.RyuVsGuile)
- [x] sfiii3n MAX_HEALTH fixed (176→160)
- [x] sf2ce game adapter created (delta-based round detection, MAX_HEALTH=176)
- [x] RetroEngine updated (Actions.FILTERED, dual-format _translate_info, simplified _integration_path)
- [x] config.py retro_game set to SF2 Genesis
- [x] Health check uses stable_retro import
- [x] E2E smoke test passed in WSL2 (full bo3, 2538 FPS)
- [x] Inference pipeline aligned (84x84x4 grayscale, CnnPolicy, frame stacking)
- [x] Trained SF2 models available (PPO, 200K–2M step checkpoints)
- [x] Pretrained community models imported (linyiLYi, thuongmhh)
- [x] Multi-model auto-detection in live viewer
- [x] Live match viewer with sidebar HUD, input overlay, scrolling log
- [x] Training script with asymmetric reward and tuned hyperparams
- [x] Match-to-settlement integration (models → match → stream → hash → resolve → claim)
- [x] WebSocket video and data streams published to Redis (browser test pending full stack run)
- [x] Elo system assigns correct ratings after calibration

---

## Phase 3: Testing Suite

Build confidence before deploying anywhere.

### 3.1 Backend Integration Tests ✅ COMPLETE

76 integration tests across 16 files, all passing. Tests use SQLite in-memory DB (with UUID→VARCHAR compat layer), mocked Redis/Solana/Celery, and FastAPI's httpx AsyncClient.

**Test infrastructure (`tests/conftest.py`):**
- In-memory SQLite via aiosqlite (no external DB needed)
- SQLiteTypeCompiler patch for PostgreSQL UUID → VARCHAR(36)
- Per-test rollback isolation via SQLAlchemy async sessions
- In-memory Redis mock (sorted sets, pipeline, scan with fnmatch)
- Noop lifespan (skips Redis/Solana/AccountListener init)
- Seed fixtures: 2 users, 4 fighters, 3 matches, 2 bets
- Auth helpers: internal JWT, API key headers

**Test files created:**

| File | Tests | Coverage |
|------|-------|---------|
| `test_api/test_matches.py` | 11 | List, paginate, filter by status/game, get, create with auth |
| `test_api/test_fighters.py` | 6 | List (ready only, sorted, filtered), get |
| `test_api/test_bets.py` | 7 | List by wallet/match, record bet, duplicates, not-found/not-open |
| `test_api/test_odds.py` | 3 | Pool odds calculation, zero sides, not found |
| `test_api/test_leaderboard.py` | 5 | Sorted by elo, ready-only, divisions, limit |
| `test_api/test_middleware.py` | 5 | Internal JWT (valid/expired/missing/invalid), rate limiting |
| `test_gateway/test_auth.py` | 8 | derive_api_key, hash_api_key, validate_api_key |
| `test_gateway/test_register.py` | 3 | Register success, invalid sig, duplicate |
| `test_gateway/test_submit.py` | 4 | Submit fighter, unknown game, no auth, rate limit |
| `test_gateway/test_match.py` | 8 | Queue (success/not-owned/not-ready/game-mismatch), custom match (4) |
| `test_gateway/test_fighters.py` | 4 | List owned, get not-owned, recalibrate success/wrong-status |
| `test_services/test_match_queue.py` | 5 | Enqueue/dequeue, try_match, self-match block, elo gap, widen |
| `test_services/test_anti_manipulation.py` | 5 | Concentration alert, cross-wallet, high winrate audit |

**Production bugs found and fixed during testing:**
- `main.py` — `RateLimitMiddleware` was defined but never registered in `create_app()`
- `services/anti_manipulation.py` — String `match_id` not converted to `uuid.UUID` before UUID column comparison

**Total test suite: 252 tests (250 pass, 2 pre-existing Solana deserialization failures)**

### 3.2 Existing Unit Tests (from Phase 2)

176 unit tests already existed covering:
- Game adapters (sfiii3n, sf2ce, kof98, tektagt) — state extraction, round/match detection
- Engine internals — match runner, frame processing, replay recording
- Elo math — rating updates, K-factors, division placement, seasonal reset
- Calibration — reference match scoring, status transitions
- Solana — PDA derivation, account deserialization

### 3.3 Frontend Tests

Still pending:
- Component tests with Vitest + React Testing Library
- Hook tests (useMatchVideoStream, useMatchDataStream, usePlaceBet, useClaimPayout)
- Store tests (matchStore, walletStore)
- Page rendering tests with mock API data

### 3.4 Contract Tests

Still pending:
- Extend existing 14 tests with edge cases
- Timeout match flow
- Sweep unclaimed/cancelled bets
- Fee withdrawal after claim window
- Close match + bet PDA rent reclamation
- Overflow protection in payout math

### 3.5 Load Testing

Still pending:
- Concurrent match execution (target: 8 simultaneous across 8 Celery workers)
- WebSocket connection limits (video: 2/IP, data: 5/IP)
- Bet throughput under contention
- Match queue with 50+ fighters
- Note: One emulator per process — concurrent matches = concurrent worker processes

### Phase 3 Checklist
- [x] Backend integration test suite (76 tests, all API + gateway + services)
- [x] Backend unit tests (176 tests, adapters + engine + elo + solana)
- [x] Total: 252 tests (250 passing, 2 pre-existing Solana failures)
- [ ] Frontend component tests pass
- [ ] Contract tests cover all 15 instructions
- [ ] Load test results documented with bottlenecks identified

---

## Phase 4: CI/CD Pipeline ✅ COMPLETE

Automate quality gates.

### 4.1 GitHub Actions Workflows ✅

Three workflows created in `.github/workflows/`:

- **`lint.yml`** — Ruff check + format check (backend), ESLint (frontend)
- **`test.yml`** — pytest with Postgres 16 + Redis 7 services (backend), `npm run build` (frontend)
- **`build.yml`** — Docker image builds for backend + worker, push to GHCR on main push

### 4.2 Docker Images ✅

- **Backend** (`Dockerfile`) — Python 3.11-slim, lightweight (no PyTorch/stable-retro), ~500MB, port 8080
- **Worker** (`Dockerfile.worker`) — Python 3.11-slim + cmake + emulation deps (stable-retro, SB3, PyTorch), ~4GB, ROM mounted at runtime
- **Dep split** — `pyproject.toml` has `[emulation]` optional extra; backend installs base, worker installs `.[emulation]`
- **Layer caching** — Dependencies installed before source copy; code changes don't re-download packages
- **Registry** — GitHub Container Registry (`ghcr.io/$REPO/backend`, `ghcr.io/$REPO/worker`)
- Added `.dockerignore` to exclude tests, venvs, logs

### 4.3 K8s Manifests Updated ✅

- Backend deployment: port 8000 → 8080 (matches actual backend port)
- Worker deployment: removed `nvidia.com/gpu` (emulation is CPU-only, no GPU needed)

### 4.4 Notes

- Clippy (contracts) skipped — requires Solana platform-tools which are complex for CI; can add later
- Anchor test skipped — requires Solana test validator running; can add with a dedicated CI environment
- Vitest (frontend) skipped — no test files yet; will add in Phase 3 backfill
- Branch protection — configure manually in GitHub repo settings

### Phase 4 Checklist
- [x] Lint workflow (Ruff + ESLint) created and pushed
- [x] Test workflow (pytest + frontend build) created and pushed
- [x] Build workflow (Docker → GHCR) created and pushed
- [x] Dockerfiles updated (port 8080, cmake deps, no docker.io)
- [x] K8s manifests fixed (port 8080, no GPU)
- [ ] Branch protection rules enforced (manual GitHub config)
- [ ] Verify CI passes on first run

---

## Phase 5: Staging Deployment — IN PROGRESS

Real infrastructure on Railway + Vercel + Cloudflare R2.

### 5.1 Solana Devnet ✅ COMPLETE

Contracts deployed to devnet (2026-02-17):
- Program ID: `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K`
- PlatformConfig initialized (3% fee, 30min timeout)
- Oracle funded: `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4`

### 5.2 Cloudflare R2 (S3 Storage) — Partial

- `rawl-replays` bucket created via wrangler CLI
- Account ID: `c6628f14128b74475ed944e9c3e47c5d`
- **TODO**: Create R2 API token via dashboard (wrangler doesn't support token creation)
- **TODO**: Set `S3_ACCESS_KEY` and `S3_SECRET_KEY` env vars on Railway

### 5.3 Railway (Backend) — Deploying

Project `rawl-staging` with 3 services connected to GitHub repo:

| Service | Dockerfile | Start Command |
|---------|-----------|--------------|
| backend | `Dockerfile` (lightweight, no PyTorch) | `uvicorn rawl.main:create_app --factory --host 0.0.0.0 --port 8080` |
| worker | `Dockerfile.worker` (full, with emulation deps) | `celery -A rawl.celery_app worker -l info --pool=prefork --concurrency=2` |
| beat | `Dockerfile` (lightweight) | `celery -A rawl.celery_app beat -l info` |

Backend URL: `https://backend-production-23925.up.railway.app`

**Dependency split**: Backend API doesn't need PyTorch/stable-retro (~4GB). Only the worker needs `.[emulation]` extras. This makes backend builds ~1 min vs ~5 min for worker.

**Docker layer caching**: Dependencies installed before source copy. Code-only changes don't re-download packages.

Managed services (Railway-provisioned):
- PostgreSQL: `postgres.railway.internal:5432`
- Redis: `redis.railway.internal:6379`

Env vars set on all 3 services via `railway variables set`.
Oracle keypair loaded via `ORACLE_KEYPAIR_JSON` env var.

**TODO**: Run `alembic upgrade head` after backend deploys successfully.

### 5.4 Vercel (Frontend) ✅ LIVE

- Production URL: **https://rawl-frontend.vercel.app**
- Connected to GitHub repo (`rawl-the-claw-club`), auto-deploys on push
- Root directory: `packages/frontend`
- `@rawl/shared` types inlined into frontend (Vercel can't access cross-package `file:` deps)
- Env vars: `NEXT_PUBLIC_PROGRAM_ID`, `NEXT_PUBLIC_SOLANA_RPC_URL`, `NEXT_PUBLIC_SOLANA_NETWORK`, `NEXT_PUBLIC_API_URL`

### 5.5 DNS + TLS

- Railway and Vercel both provide HTTPS automatically
- Custom domain not yet configured
- CORS_ORIGINS updated to include Vercel URL

### 5.6 Docker Image Optimization

Dependencies split between backend API and worker to avoid unnecessary PyTorch downloads:

| Image | Size | Deps | Build Time |
|-------|------|------|-----------|
| Backend (`Dockerfile`) | ~500MB | FastAPI, SQLAlchemy, Celery, Solana, etc. | ~1 min |
| Worker (`Dockerfile.worker`) | ~4GB | Above + stable-retro, stable-baselines3, PyTorch | ~5 min |

`pyproject.toml` uses optional `[emulation]` extra for worker-only deps (opencv, stable-retro, stable-baselines3).

### Phase 5 Checklist
- [x] Contracts deployed to Solana devnet
- [x] PlatformConfig initialized on-chain
- [x] Oracle funded on devnet
- [x] Cloudflare R2 bucket created
- [x] Railway project created with 3 services
- [x] Railway PostgreSQL + Redis provisioned
- [x] All env vars configured on Railway
- [x] Vercel frontend deployed and live
- [x] GitHub repo connected for auto-deploys (both Railway + Vercel)
- [x] Docker images optimized (dep split, layer caching)
- [ ] R2 API token created (dashboard)
- [ ] Railway builds pass and services healthy
- [ ] Database migrated on Railway (`alembic upgrade head`)
- [ ] NEXT_PUBLIC_API_URL updated with final Railway URL
- [ ] End-to-end smoke test on staging
- [ ] Custom domain configured (optional)

---

## Phase 6: Monitoring & Observability

See what's happening before going live.

1. **Grafana dashboards** (4 specified in SDD)
   - **Platform Overview** — Active matches, connected users, bet volume, system health
   - **Match Operations** — Match duration, inference latency, frame rates, error rates
   - **Fighter Ecosystem** — Checkpoint submissions, validation pass rates, Elo distribution
   - **Financial Operations** — Bet volume, payout amounts, fee collection, refund rates

2. **Prometheus**
   - Scrape config for backend `/api/internal/metrics`
   - Node exporter for system metrics

3. **Alerting**
   - PagerDuty or OpsGenie integration
   - P1 alerts: oracle failure, emulation engine crash, Solana RPC down, database connection loss
   - P2 alerts: high error rates, queue depth, checkpoint validation failures

4. **Incident runbooks**
   - Platform authority key compromise
   - Oracle signing failure
   - Emulation engine failure / ROM corruption
   - Solana RPC downtime
   - Database failover procedure

### Phase 6 Checklist
- [ ] All 4 Grafana dashboards configured and populated
- [ ] Prometheus scraping all services
- [ ] P1 alert rules firing correctly
- [ ] Incident runbooks reviewed and accessible

---

## Phase 7: Production Launch

Go live.

1. **Solana mainnet deployment**
   - Deploy contracts to mainnet-beta
   - Fund oracle wallet with SOL for transaction fees
   - Configure platform authority (ideally HSM-backed)
   - Set platform fee (300 BPS = 3%)

2. **Security hardening**
   - Oracle keypair in HSM or secure vault
   - Rate limiting verified and tuned
   - Anti-manipulation checks active (concentration alerts, cross-wallet detection)
   - API key rotation procedures documented
   - Internal JWT secret rotation (quarterly)
   - Checkpoint validation sandboxing verified (untrusted model code isolation)

3. **Open-source training package**
   - Publish pip-installable `rawl-trainer` package
   - Includes: stable-retro env wrapper, obs preprocessing, PPO config, macro action wrapper
   - Documentation: action space spec, checkpoint format, submission API
   - Example training script + Colab notebook

4. **Mobile responsive UI**
   - Frontend is desktop-only — needs responsive breakpoints
   - Arena page: stack video/betting vertically on mobile
   - Lobby/leaderboard: responsive tables/cards

5. **Soft launch**
   - Limited user access (allowlist or invite codes)
   - SF2: Special Champion Edition (Genesis) as sole launch title
   - Monitor all dashboards closely
   - Rapid bug fix cycle
   - Gradually increase user cap

### Phase 7 Checklist
- [ ] Contracts live on Solana mainnet
- [ ] Oracle funded and signing correctly
- [ ] Security audit completed (internal or external)
- [ ] Training package published and documented
- [ ] Mobile UI works on common screen sizes
- [ ] Soft launch users onboarded successfully

---

## Phase 8: Post-Launch (v2+ Roadmap)

Future enhancements.

- **Additional game titles** — SF3 3rd Strike (Dreamcast / Flycast or FBNeo arcade), KOF98 (Neo Geo / FBNeo core), MK2 (Arcade / FBNeo), other fighting games via stable-retro integrations
- **SPL token support** — USDC and other SPL tokens for betting (requires additional program logic for token accounts)
- **Multi-sig oracle** — Multiple independent operators signing match results
- **HSM key storage** — Hardware security module for platform authority keypair
- **Advanced anti-manipulation** — Graph analysis for Sybil detection, cross-wallet funding patterns
- **Verifiable computation proofs** — Cryptographic proof of match execution integrity
- **On-chain fighter ownership** — NFT-based fighter registration for trustless self-match prevention
- **Agent self-betting analytics** — Dashboard showing AI agent wagering patterns as market signals
- **Custom training algorithms** — Community-contributed training configs beyond PPO (A3C, DQN, etc.)

---

## Quick Reference

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Local dev environment | ✅ Complete |
| 2 | Integration testing & bugs | ✅ Complete |
| 3 | Test suite | In Progress (backend ✅, frontend/contracts pending) |
| 4 | CI/CD | ✅ Complete |
| 5 | Staging deployment | In Progress (Solana ✅, Vercel ✅, Railway deploying) |
| 6 | Monitoring | Pending |
| 7 | Production launch | Pending |
| 8 | Post-launch roadmap | Future |

## Service Quick-Start Commands

```bash
# 1. Stop local PostgreSQL (if running)
net stop postgresql-x64-18

# 2. Docker services
cd /c/Projects/Rawl && docker compose up -d

# 3. Backend (port 8080)
cd packages/backend && uvicorn rawl.main:create_app --factory --reload --host 0.0.0.0 --port 8080

# 4. Frontend
cd packages/frontend && npm run dev

# 5. Solana validator (in WSL)
wsl -d Ubuntu-22.04 -- bash -c 'export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH" && solana-test-validator --reset --ledger /tmp/rawl-test-ledger'

# 6. Celery worker
cd packages/backend && celery -A rawl.celery_app worker --loglevel=info --pool=solo

# 7. Celery beat
cd packages/backend && celery -A rawl.celery_app beat --loglevel=info

# Health check
curl -s http://localhost:8080/api/health | python -m json.tool
```
