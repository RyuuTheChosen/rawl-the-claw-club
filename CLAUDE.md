# Rawl Platform

## Project Structure
Monorepo with 4 packages:
- `packages/backend/` — Python (FastAPI + ARQ + multiprocessing emulation worker)
- `packages/frontend/` — Next.js 14 (App Router) + Zustand + Tailwind + wagmi/RainbowKit
- `packages/contracts/` — Solidity (Foundry) smart contracts on Base
- `packages/shared/` — Shared TypeScript types

Other top-level dirs: `scripts/`, `docs/`. Authoritative spec: `Rawl_SDD.md`

## Quick Start
1. `docker compose up -d` — PostgreSQL, Redis, MinIO
2. `cd packages/backend && alembic upgrade head` — migrations
3. `make dev-backend` — API on port 8080
4. `make dev-worker` — ARQ worker (cron + async tasks, runs on Windows)
5. `make dev-emulation` — Emulation worker (requires Linux/WSL2 — stable-retro)
6. `make dev-frontend` — Next.js on port 3000

All commands: `make help`. Stop local Postgres if port conflicts: `net stop postgresql-x64-18`

## Deployment
- **Local-first** — all services run locally via `docker compose` + `make dev-*`
- **Contracts**: Base Sepolia (chain ID 84532) — Foundry/Forge
- **Local chain**: Anvil (`anvil --fork-url $BASE_SEPOLIA_RPC`) for dev/testing
- **Deploy contracts**: `./scripts/deploy-base.sh` (needs `BASE_SEPOLIA_RPC`, `BASESCAN_API_KEY`)

## Architecture
- Backend runs on **port 8080**
- Emulation is in-process via RetroEngine (`engine/emulation/retro_engine.py`), no Docker/gRPC
- Training is off-platform — users run `rawl-trainer` on their own GPUs
- Match engine flow: validate_info → lock_match → game loop → hash → MinIO/S3 → resolve_match
- Game adapters: per-game modules (`sf2ce`, `sfiii3n`, `kof98`, `tektagt`) + stubs (`doapp`, `umk3`)
- WebSocket streaming: video (binary H.264 30fps, types: SEQ_HEADER/KEYFRAME/DELTA/EOS) + data (JSON 10Hz)
- All match results hashed and uploaded to MinIO (local) before on-chain resolution
- On-chain: `RawlBetting.sol` (EVM) — AccessControl + ReentrancyGuard + Pausable (OpenZeppelin v5)
- Backend chain client: `rawl.evm.client.EVMClient` (web3.py v7, async)
- Frontend wallet: wagmi v2 + viem v2 + RainbowKit v2 (Coinbase Wallet, MetaMask, WalletConnect)
- Task queue: ARQ (`rawl.arq_app.WorkerSettings`) — cron runs inline, no separate beat process
- Emulation: `rawl.engine.emulation_worker` — multiprocessing consumer, LMOVE for crash-safe job claim
- Emulation queue: 6 Redis keys under `rawl:emulation:*` (sorted set + hash for deferred, lists for active)
- ARQ cron: schedule_matches (30s), promote_ready (5s), heartbeats (60s), reconcile (60s), retry_uploads (5min), seasonal_reset (quarterly)

## Conventions
- Python: Ruff (line-length=100, py311), asyncio, Pydantic
- Solidity: Foundry, solc 0.8.24, optimizer 200 runs, custom errors (not require strings)
- TypeScript: ESLint, strict mode
- All API responses use cursor-based pagination
- `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
- Match IDs: UUID → bytes32 via `uuid.hex.ljust(64, '0')` (same in backend + frontend)
- Amounts: wei (uint256 on-chain), stored as `amount_eth: float` in DB
- Wallet addresses: EVM format `0x` + 40 hex chars (max_length=42)

## Environment
- Python >=3.11, Node >=20, Foundry (forge, cast, anvil)
- Config: env vars or `.env` (see `config.py`). Root `.env.example` has defaults.
- Local services: PostgreSQL (5432), Redis (6379), MinIO (9000)
- Base chain: `BASE_RPC_URL`, `ORACLE_PRIVATE_KEY`, `CONTRACT_ADDRESS`, `BASE_CHAIN_ID`
- Frontend env: `packages/frontend/.env.local` (NEXT_PUBLIC_CONTRACT_ADDRESS, BASE_RPC_URL, CHAIN_ID, REOWN_PROJECT_ID)

## Contracts (Foundry)
- `packages/contracts/src/RawlBetting.sol` — Main contract
- `packages/contracts/test/` — Unit, fuzz, invariant tests
- `packages/contracts/script/Deploy.s.sol` — Deployment script
- Build: `make contracts-build` / Test: `make contracts-test` / Install deps: `make contracts-install` (lib/ is gitignored)
- Roles: ORACLE_ROLE (create/lock/resolve), ADMIN_ROLE (cancel/withdraw/sweep/config)
- 14 functions, gas-optimized packed structs (MatchPool: 6 slots, BetInfo: 1 slot); `via_ir = true` required (stack too deep)

## Scripts
WSL2 scripts: `wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/c/Projects/Rawl && python3 scripts/<name>.py"`
- `watch_match.py`, `train_sf2_baseline.py`, `test_stable_retro.py`

Native scripts: `deploy-base.sh`, `test-betting-flow-evm.py`, `seed-db.py`, `upload_pretrained_models.py`, `railway_config.py`

## Common Gotchas
- `match_format` must be int (3), not string ("bo3"), everywhere
- EVM nonce management: NonceManager with asyncio.Lock, rollback on failure, reset on "nonce too low"
- `evm_client.reset()` MUST be sync (called before `asyncio.run()` in subprocess workers)
- `bet_exists()` returns True/False/None (None = RPC error) — callers must handle all three states
- Fee BPS snapshotted at match creation — global config changes don't affect in-flight matches
- CEI pattern on all ETH transfers (state change before external call)
- stable-retro do NOT work on Windows — use **WSL2**
- Backend CORS default is `http://localhost:3000` — must match frontend origin
- `import retro` deprecated — use `import stable_retro`
- Frame stacking `FRAME_STACK_N=4` must match training `VecFrameStack(n_stack=4)` — mismatch silently breaks inference
- Model expects `(84, 84, 4)` obs (84x84x1 grayscale, stacked x4) — `CnnPolicy` not `MlpPolicy`
- Use `Actions.FILTERED` (not `MULTI_DISCRETE` — has 2P bug)
- Frontend `GameId` in `types/index.ts` must include all active games — `sf2ce` is launch title
- Emulation: SF2 Champion Edition Genesis (`genesis_plus_gx`), MAX_HEALTH=176, `MultiBinary(24)`
- WSL2 headless: `SDL_VIDEODRIVER=dummy` + `render_mode='rgb_array'`
- RetroEngine: 256x256 raw → `preprocess_for_inference()` → 84x84 grayscale
