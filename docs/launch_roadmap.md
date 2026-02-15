# Rawl Platform — Launch Roadmap

> Phased guide to go from codebase to production. Current state: ~95% code written, ~0% running in production.

---

## Phase 1: Local Dev Environment Setup

Get everything running on your machine.

1. **Docker services** — Start PostgreSQL, Redis, MinIO
   ```bash
   docker compose up -d
   ```

2. **Database** — Run migrations and seed data
   ```bash
   cd packages/backend
   alembic upgrade head
   python scripts/seed-db.py
   ```

3. **Environment** — Copy and configure secrets
   ```bash
   cp .env.example .env
   # Fill in: DATABASE_URL, REDIS_URL, S3 credentials, Solana RPC, JWT secret, etc.
   ```

4. **Backend** — Start FastAPI dev server
   ```bash
   cd packages/backend
   uvicorn rawl.main:create_app --factory --reload
   ```

5. **Frontend** — Install deps and start Next.js
   ```bash
   cd packages/frontend
   npm install
   npm run dev
   ```

6. **Solana test validator** — Local blockchain + deploy contracts
   ```bash
   solana-test-validator
   # In another terminal:
   cd packages/contracts
   anchor build
   anchor deploy
   ```

7. **Celery workers** — Start worker and beat scheduler
   ```bash
   cd packages/backend
   celery -A rawl.celery_app worker --loglevel=info
   celery -A rawl.celery_app beat --loglevel=info
   ```

8. **DIAMBRA** — Install engine and at least one ROM
   - Install DIAMBRA Engine (Docker-based)
   - Place sfiii3n ROM in configured ROM path
   - Verify with a test environment launch

### Phase 1 Checklist
- [ ] Docker services healthy (`docker compose ps`)
- [ ] Database migrated and seeded
- [ ] `.env` configured with all required vars
- [ ] Backend responds at `http://localhost:8000/api/health`
- [ ] Frontend loads at `http://localhost:3000`
- [ ] Solana test validator running, contracts deployed
- [ ] Celery worker and beat running
- [ ] DIAMBRA engine launches successfully

---

## Phase 2: Integration Testing & Bug Fixing

Verify the pieces actually work together. This is likely the longest phase.

1. **Match execution end-to-end**
   - Queue two fighters via gateway API
   - Match scheduler picks them up, creates on-chain pool
   - Match runner loads models, runs DIAMBRA game loop
   - Verify video WebSocket streams MJPEG frames
   - Verify data WebSocket streams 16-field JSON at 10Hz
   - Verify replay saved to S3 (MJPEG + JSON sidecar + frame index)
   - Verify match result hashed and submitted on-chain

2. **Betting flow**
   - Place bets on both sides via frontend wallet
   - Verify betting window enforcement (5 min default)
   - Verify min bet enforcement (0.01 SOL)
   - Lock match, resolve with winner
   - Claim payout, verify proportional distribution
   - Test cancel flow: cancel match → refund bets

3. **Training pipeline**
   - Register a fighter via gateway API
   - Submit model for training (Free tier: T4, 500K steps)
   - Verify PPO self-play runs in DIAMBRA
   - Monitor progress via training WebSocket
   - Verify 4-step model validation on completion
   - Download trained model from S3

4. **Elo & calibration**
   - Run calibration matches against 5 reference fighters
   - Verify min 3/5 success requirement
   - Check Elo assignment and division placement
   - Test adaptive K-factors (40 → 20 → 16)

5. **Frontend ↔ Backend**
   - Lobby page loads matches with correct status filters
   - Arena page streams live match video + data overlay
   - Betting panel submits transactions via wallet
   - Leaderboard shows correct division rankings
   - Dashboard shows user's fighters, training jobs, bets
   - Fighter profile shows stats and match history

6. **Fix bugs** — Document and resolve all integration issues

### Phase 2 Checklist
- [ ] Full match runs start-to-finish without errors
- [ ] WebSocket video and data streams work in browser
- [ ] Betting → resolve → payout works on local Solana
- [ ] Training pipeline produces valid model
- [ ] Elo system assigns correct ratings after calibration
- [ ] All frontend pages render with real backend data
- [ ] Wallet connect + bet submission works end-to-end

---

## Phase 3: Testing Suite

Build confidence before deploying anywhere.

1. **Backend integration tests**
   - Full match execution pipeline (mock DIAMBRA or use lightweight env)
   - Training pipeline end-to-end
   - All API endpoints (public + gateway)
   - WebSocket streaming (video + data channels)
   - Celery task execution (scheduler, health checker, upload retry)

2. **Frontend tests**
   - Component tests with Vitest + React Testing Library
   - Hook tests (useMatchVideoStream, useMatchDataStream)
   - Store tests (matchStore, walletStore)
   - Page rendering tests with mock API data

3. **Contract tests**
   - Extend existing 14 tests with edge cases
   - Timeout match flow
   - Sweep unclaimed/cancelled bets
   - Fee withdrawal after claim window
   - Close match + bet PDA rent reclamation
   - Overflow protection in payout math

4. **Load testing**
   - Concurrent match execution (target: 8 simultaneous)
   - WebSocket connection limits (video: 2/IP, data: 5/IP)
   - Bet throughput under contention
   - Match queue with 50+ fighters

### Phase 3 Checklist
- [ ] Backend test suite passes with >80% coverage on critical paths
- [ ] Frontend component tests pass
- [ ] Contract tests cover all 15 instructions
- [ ] Load test results documented with bottlenecks identified

---

## Phase 4: CI/CD Pipeline

Automate quality gates.

1. **GitHub Actions workflows**
   - `lint.yml` — Ruff (backend), ESLint + Prettier (frontend), Clippy (contracts)
   - `test.yml` — pytest, vitest, anchor test
   - `build.yml` — Docker image build for backend + worker

2. **Docker image builds**
   - Backend image (FastAPI + uvicorn)
   - Worker image (Celery + DIAMBRA dependencies)
   - Push to container registry (ECR, GCR, or Docker Hub)

3. **Branch protection**
   - Require passing CI before merge to main
   - Require at least 1 review on PRs

### Phase 4 Checklist
- [ ] All CI checks pass on main branch
- [ ] Docker images build and push automatically
- [ ] Branch protection rules enforced

---

## Phase 5: Staging Deployment

Real infrastructure, not production yet.

1. **Infrastructure as Code**
   - Terraform modules for GPU VMs (T4 for matches/training, A10G for Pro tier)
   - VPC, security groups, load balancers
   - Managed PostgreSQL (RDS/Cloud SQL)
   - Managed Redis (ElastiCache/Memorystore)
   - S3 bucket with lifecycle policies

2. **Kubernetes deployment**
   - Use existing manifests in `infra/k8s/`
   - Backend: 2+ replicas with readiness probes
   - Workers: GPU-enabled nodes with T4/A10G selectors
   - Account listener: 1 replica
   - Add HPA for backend auto-scaling

3. **Frontend hosting**
   - Deploy to Vercel or Cloudflare Pages
   - Configure environment variables (API URL, Solana RPC, program ID)
   - Set up preview deployments for PRs

4. **Solana devnet**
   - Deploy contracts to devnet
   - Configure oracle keypair
   - Fund oracle and test wallets with devnet SOL

5. **DNS + TLS**
   - Domain setup (e.g., staging.rawl.gg)
   - HTTPS via Let's Encrypt or managed certificates
   - CORS origin configuration

### Phase 5 Checklist
- [ ] Terraform applies cleanly to staging environment
- [ ] Backend + workers running on Kubernetes with GPU access
- [ ] Frontend deployed and accessible via staging URL
- [ ] Contracts deployed to Solana devnet
- [ ] End-to-end flow works on staging (match + betting + training)

---

## Phase 6: Monitoring & Observability

See what's happening before going live.

1. **Grafana dashboards** (4 specified in SDD)
   - **Platform Overview** — Active matches, connected users, bet volume, system health
   - **Match Operations** — Match duration, inference latency, frame rates, error rates
   - **Training Pipeline** — Active jobs, GPU utilization, training throughput, validation results
   - **Financial Operations** — Bet volume, payout amounts, fee collection, refund rates

2. **Prometheus**
   - Scrape config for backend `/api/internal/metrics`
   - Node exporter for system metrics
   - GPU metrics (nvidia-smi exporter)

3. **Alerting**
   - PagerDuty or OpsGenie integration
   - P1 alerts: oracle failure, DIAMBRA crash, Solana RPC down, database connection loss
   - P2 alerts: high error rates, queue depth, training failures

4. **Incident runbooks**
   - Platform authority key compromise
   - Oracle signing failure
   - DIAMBRA cluster outage
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

3. **Remaining game adapters**
   - Implement UMK3 adapter (currently stub)
   - Implement DOAPP adapter (currently stub)
   - Requires DIAMBRA ROM testing and health/round extraction logic

4. **Mobile responsive UI**
   - Frontend is desktop-only — needs responsive breakpoints
   - Arena page: stack video/betting vertically on mobile
   - Lobby/leaderboard: responsive tables/cards

5. **Soft launch**
   - Limited user access (allowlist or invite codes)
   - Monitor all dashboards closely
   - Rapid bug fix cycle
   - Gradually increase user cap

### Phase 7 Checklist
- [ ] Contracts live on Solana mainnet
- [ ] Oracle funded and signing correctly
- [ ] Security audit completed (internal or external)
- [ ] All 5 game adapters functional
- [ ] Mobile UI works on common screen sizes
- [ ] Soft launch users onboarded successfully

---

## Phase 8: Post-Launch (v2+ Roadmap)

Future enhancements defined in SDD.

- **SPL token support** — USDC and other SPL tokens for betting (requires additional program logic for token accounts)
- **Multi-sig oracle** — Multiple independent operators signing match results
- **HSM key storage** — Hardware security module for platform authority keypair
- **BYO model uploads** — Users bring their own pre-trained models (SDD Stage 3)
- **Custom training algorithms** — Beyond PPO, user-selectable training configs (SDD Stage 3)
- **Advanced anti-manipulation** — Graph analysis for Sybil detection, cross-wallet funding patterns
- **Verifiable computation proofs** — Cryptographic proof of match execution integrity (SDD v3)
- **On-chain fighter ownership** — NFT-based fighter registration for trustless self-match prevention

---

## Quick Reference

| Phase | Focus | Estimated Effort |
|-------|-------|-----------------|
| 1 | Local dev environment | Setup & config |
| 2 | Integration testing & bugs | Heaviest phase |
| 3 | Test suite | Quality assurance |
| 4 | CI/CD | Automation |
| 5 | Staging deployment | Infrastructure |
| 6 | Monitoring | Observability |
| 7 | Production launch | Go live |
| 8 | Post-launch roadmap | Future features |
