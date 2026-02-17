# Rawl Platform — Devnet Deployment Guide

> Step-by-step guide to deploy Rawl to Solana devnet with Railway (backend) + Vercel (frontend).

---

## Deployment Status

| Component | Status | Details |
|-----------|--------|---------|
| Solana devnet contract | **Deployed** | Program `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` |
| PlatformConfig | **Initialized** | PDA `CvKx2cxZBYwUUqjFE73s5KggNntgQth5yAWhSLDuPTUj`, 3% fee, 30min timeout |
| Oracle wallet | **Funded** | `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4` (0.998 SOL) |
| Deployer wallet | **Funded** | `HUssQyZHW2jRuAG6qeuvcDu93w5TYZfDecsSwVwyjAjd` (1.33 SOL) |
| Cloudflare R2 | Pending | S3-compatible storage for replays/models |
| Railway (backend) | Pending | FastAPI + Celery |
| Vercel (frontend) | Pending | Next.js 14 |

**Deployed:** 2026-02-17

**Transactions:**
- Program deploy: `3XDL7tFVieHbtk4DzELsNYGQJiLTGrs6XHy3cjYdW9zJKRoGtz8ViCuBgeCJRFZQMpVzieVAZpm7k3nkJ3BPNjdQ`
- Oracle fund (1 SOL transfer): `4fnXLa9TqkypRB55BKAH4iZ94g6zTHWjf75wiQu2mBCMku3pRKWDDep4YEZMpNfNU8s7jVCD4VUQzWcUXFUTmjFU`
- PlatformConfig init: `5nirLUmbvvmQsFnYLCFjY6QNz2232Gxpumy82PNDLsjZQT6jDTQAWmLscsoCHGcWaYGFEjBnuZ44Arbz2Jyq3sbx`

**Explorer links:**
- Program: https://explorer.solana.com/address/AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K?cluster=devnet
- PlatformConfig: https://explorer.solana.com/address/CvKx2cxZBYwUUqjFE73s5KggNntgQth5yAWhSLDuPTUj?cluster=devnet

---

## Architecture Overview

```
                    ┌──────────────┐
                    │   Vercel      │
                    │  (Frontend)   │
                    │  Next.js 14   │
                    └──────┬───────┘
                           │ HTTPS
                           ▼
┌──────────────────────────────────────────┐
│              Railway                      │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Backend   │  │ Worker   │  │ Beat   │ │
│  │ (FastAPI) │  │ (Celery) │  │(Celery)│ │
│  │ port 8080 │  │ prefork  │  │        │ │
│  └─────┬─────┘  └────┬─────┘  └───┬────┘ │
│        │              │            │      │
│  ┌─────┴──────┐  ┌───┴─────┐           │
│  │ PostgreSQL  │  │  Redis   │           │
│  │ (managed)   │  │(managed) │           │
│  └─────────────┘  └──────────┘           │
└──────────────────────────────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│ Cloudflare R2 │    │  Solana Devnet    │
│ (S3 storage)  │    │  (contracts)      │
│ replays+models│    │  betting pools    │
└──────────────┘    └──────────────────┘
```

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| GitHub account | Repo hosting, CI/CD |
| Railway account | Backend hosting (https://railway.app) |
| Vercel account | Frontend hosting (https://vercel.com) |
| Cloudflare account | R2 storage (https://dash.cloudflare.com) |
| WSL2 + Solana CLI | Contract deployment |

---

## Step 1: Deploy Contracts to Solana Devnet ✅ COMPLETE

> Deployed 2026-02-17. Steps below are for reference or redeployment.

### 1.1 Fund the Deployer Wallet

The deployer wallet in WSL2 needs ~3 SOL for program deployment.

```bash
# Get your deployer address
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana address
'
```

Go to https://faucet.solana.com/ and request devnet SOL for your address. You need at least **3 SOL** (program is 375KB, deployment costs ~2.6 SOL in rent).

Alternatively, via CLI (may be rate-limited):
```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url https://api.devnet.solana.com
  solana airdrop 2
  sleep 5
  solana airdrop 2
  solana balance
'
```

### 1.2 Deploy the Program

```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url https://api.devnet.solana.com

  solana program deploy \
    /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl.so \
    --program-id /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl-keypair.json
'
```

Expected output:
```
Program Id: AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K
```

### 1.3 Fund the Oracle Wallet

```bash
# Get oracle address from the keypair
cd /c/Projects/Rawl
python -c "import json; data=json.load(open('oracle-keypair.json')); from solders.keypair import Keypair; print(Keypair.from_bytes(bytes(data)).pubkey())"
```

Fund the oracle address with ~2 SOL from https://faucet.solana.com/ (the oracle signs transactions for locking/resolving matches).

### 1.4 Initialize PlatformConfig

```bash
cd /c/Projects/Rawl

# Set env vars to point at devnet
export SOLANA_RPC_URL=https://api.devnet.solana.com
export SOLANA_WS_URL=wss://api.devnet.solana.com
export PROGRAM_ID=AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K

python scripts/init-platform.py
```

### 1.5 Verify Deployment

```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana program show AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K --url https://api.devnet.solana.com
'
```

### 1.6 Reset Solana Config to Local

After devnet deployment, switch back so local dev still works:
```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url http://127.0.0.1:8899
'
```

**Record these values — you'll need them for Railway and Vercel env vars:**

| Key | Value |
|-----|-------|
| Program ID | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` |
| Oracle Pubkey | `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4` |
| Deployer Pubkey | `HUssQyZHW2jRuAG6qeuvcDu93w5TYZfDecsSwVwyjAjd` |

---

## Step 2: Set Up Cloudflare R2 (S3 Storage)

R2 provides S3-compatible storage with free egress. Used for replay files and model checkpoints.

### 2.1 Create R2 Bucket

1. Go to https://dash.cloudflare.com → **R2 Object Storage**
2. Click **Create bucket**
3. Name: `rawl-replays` (and optionally `rawl-models`)
4. Location: Auto or nearest region

### 2.2 Create API Token

1. Go to **R2** → **Manage R2 API Tokens**
2. Click **Create API token**
3. Permissions: **Object Read & Write**
4. Specify bucket: `rawl-replays`
5. Save the **Access Key ID** and **Secret Access Key**

### 2.3 Note the Endpoint

R2 endpoint format: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

Find your Account ID on the R2 dashboard overview page.

**Record these values:**

| Key | Value |
|-----|-------|
| S3_ENDPOINT | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| S3_ACCESS_KEY | `<your R2 access key>` |
| S3_SECRET_KEY | `<your R2 secret key>` |
| S3_BUCKET | `rawl-replays` |
| S3_REGION | `auto` |

---

## Step 3: Set Up Railway (Backend + Worker)

### 3.1 Create Railway Project

1. Go to https://railway.app and sign in with GitHub
2. Click **New Project** → **Empty Project**
3. Name it `rawl-staging`

### 3.2 Add PostgreSQL

1. Click **+ New** → **Database** → **PostgreSQL**
2. Railway auto-provisions and provides `DATABASE_URL`
3. Note: Railway Postgres URLs use `postgresql://` — our backend needs `postgresql+asyncpg://`
   - Set `DATABASE_URL` as a **variable** with the asyncpg prefix:
   - `postgresql+asyncpg://user:pass@host:port/dbname`

### 3.3 Add Redis

1. Click **+ New** → **Database** → **Redis**
2. Railway auto-provisions and provides `REDIS_URL`

### 3.4 Add Backend Service

1. Click **+ New** → **GitHub Repo** → select `rawl-the-claw-club`
2. Settings:
   - **Root Directory**: `packages/backend`
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile`
   - **Watch Paths**: `packages/backend/**`
3. Networking:
   - Click **Settings** → **Networking** → **Generate Domain**
   - This gives you a public URL like `rawl-backend-production.up.railway.app`
4. Environment Variables (see [Environment Variables](#environment-variables) section below)

### 3.5 Add Worker Service

1. Click **+ New** → **GitHub Repo** → select same repo
2. Settings:
   - **Root Directory**: `packages/backend`
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile.worker`
   - **Watch Paths**: `packages/backend/**`
3. **No networking needed** — worker connects to Redis/Postgres internally
4. Same environment variables as backend

### 3.6 Add Beat Service (Optional)

Celery Beat for periodic tasks (match scheduling, health checks).

1. Click **+ New** → **GitHub Repo** → select same repo
2. Settings:
   - **Root Directory**: `packages/backend`
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile`
   - **Watch Paths**: `packages/backend/**`
3. **Custom Start Command**: `celery -A rawl.celery_app beat --loglevel=info`
4. Same environment variables as backend

### 3.7 Run Database Migrations

In Railway dashboard, open the Backend service → **Settings** → **Execute Command**:
```bash
cd /app && python -m alembic upgrade head
```

Or use Railway CLI:
```bash
railway run --service backend -- python -m alembic upgrade head
```

### 3.8 Seed Database (Optional)

```bash
railway run --service backend -- python scripts/seed-db.py
```

---

## Step 4: Set Up Vercel (Frontend)

### 4.1 Import Project

1. Go to https://vercel.com and sign in with GitHub
2. Click **Add New** → **Project**
3. Import `rawl-the-claw-club` repository
4. Settings:
   - **Framework Preset**: Next.js
   - **Root Directory**: `packages/frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
   - **Install Command**: `npm install`

### 4.2 Environment Variables

Add these in the Vercel dashboard:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_PROGRAM_ID` | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` |
| `NEXT_PUBLIC_SOLANA_RPC_URL` | `https://api.devnet.solana.com` |
| `NEXT_PUBLIC_SOLANA_NETWORK` | `devnet` |
| `NEXT_PUBLIC_API_URL` | `https://rawl-backend-production.up.railway.app/api` |

> Replace the API URL with your actual Railway backend URL.

### 4.3 Deploy

Click **Deploy**. Vercel builds and deploys automatically. You get a URL like `rawl-frontend.vercel.app`.

Future pushes to `main` auto-deploy. PRs get preview URLs.

---

## Environment Variables

### Railway Backend + Worker + Beat

All three services share the same env vars. Set them at the **project level** in Railway so they're shared.

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | From Railway Postgres (change prefix) |
| `REDIS_URL` | `redis://...` | From Railway Redis |
| `S3_ENDPOINT` | `https://<ACCT>.r2.cloudflarestorage.com` | Cloudflare R2 |
| `S3_ACCESS_KEY` | `<R2 access key>` | From R2 API token |
| `S3_SECRET_KEY` | `<R2 secret key>` | From R2 API token |
| `S3_BUCKET` | `rawl-replays` | R2 bucket name |
| `S3_REGION` | `auto` | R2 region |
| `SOLANA_RPC_URL` | `https://api.devnet.solana.com` | Solana devnet |
| `SOLANA_WS_URL` | `wss://api.devnet.solana.com` | Solana devnet WebSocket |
| `PROGRAM_ID` | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` | Deployed program |
| `ORACLE_KEYPAIR_PATH` | `/app/oracle-keypair.json` | See note below |
| `CORS_ORIGINS` | `https://rawl-frontend.vercel.app` | Your Vercel URL |
| `INTERNAL_JWT_SECRET` | `<generate a random 64-char string>` | `openssl rand -hex 32` |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FORMAT` | `json` | |

### Oracle Keypair on Railway

The oracle keypair is a JSON file. Options for getting it into Railway:

**Option A: Environment variable (recommended for staging)**
1. Convert keypair to a single-line env var:
   ```bash
   cat oracle-keypair.json | tr -d '\n '
   ```
2. Add `ORACLE_KEYPAIR_JSON` env var in Railway
3. Add a startup script or modify `solana/client.py` to read from env var

**Option B: Mount as a file**
1. Use Railway's volume mounts to place the keypair at `/app/oracle-keypair.json`

**Option C: Bake into Docker image (NOT recommended)**
- Don't commit secrets to the image

### Vercel Frontend

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_PROGRAM_ID` | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` |
| `NEXT_PUBLIC_SOLANA_RPC_URL` | `https://api.devnet.solana.com` |
| `NEXT_PUBLIC_SOLANA_NETWORK` | `devnet` |
| `NEXT_PUBLIC_API_URL` | `https://<your-railway-url>/api` |

---

## Step 5: Smoke Test

After everything is deployed, verify the full stack:

### 5.1 Backend Health

```bash
curl -s https://<railway-backend-url>/api/health | python -m json.tool
```

Expected: all components report healthy (Solana RPC, Postgres, Redis, S3 may vary).

### 5.2 Frontend

Visit `https://<vercel-url>` — should load the lobby page.

### 5.3 Wallet Connection

1. Install Phantom wallet browser extension
2. Switch to Solana devnet (Settings → Developer Settings → Change Network → Devnet)
3. Airdrop devnet SOL to your Phantom wallet: https://faucet.solana.com/
4. Connect wallet on the Rawl frontend

### 5.4 Match Execution

```bash
# Queue two fighters via gateway API
curl -X POST https://<railway-url>/api/gateway/queue \
  -H "X-Api-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{"fighter_id": "<fighter-uuid>"}'
```

### 5.5 Betting Flow

1. Create match pool (automatic when match scheduled with `has_pool=True`)
2. Place bet via frontend (connect wallet → select side → confirm)
3. Match executes on worker
4. Oracle resolves match on-chain
5. Winner claims payout via frontend

---

## Iteration Workflow

```
Local dev (as before)
       │
   git push main
       │
       ├──→ GitHub Actions CI (lint + test + build)
       │
       ├──→ Railway auto-redeploy (backend + worker, ~3 min)
       │
       └──→ Vercel auto-redeploy (frontend, ~1 min)
```

### Making Changes

| Change Type | What Happens |
|------------|--------------|
| Backend code | Push → CI → Railway rebuilds Docker → redeploys |
| Frontend code | Push → CI → Vercel rebuilds Next.js → redeploys |
| Database schema | Push → then run `alembic upgrade head` on Railway |
| Solana contracts | Rebuild in WSL2 → `solana program deploy` to devnet |
| Environment vars | Update in Railway/Vercel dashboard → auto-restart |

### Contract Updates

Contract changes require manual redeployment:
```bash
# 1. Rebuild
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.cargo/bin:$HOME/.local/share/solana/install/active_release/bin:$PATH"
  cd /mnt/c/Projects/Rawl/packages/contracts
  cargo-build-sbf --tools-version v1.52 --manifest-path programs/rawl/Cargo.toml --sbf-out-dir target/deploy
'

# 2. Deploy to devnet
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url https://api.devnet.solana.com
  solana program deploy /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl.so \
    --program-id /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl-keypair.json
'

# 3. Switch back to local
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url http://127.0.0.1:8899
'
```

---

## Cost Estimate (Staging)

| Service | Plan | Est. Cost |
|---------|------|-----------|
| Railway (backend + worker + beat) | Hobby | ~$5-20/mo |
| Railway PostgreSQL | Included | $0 (up to 1GB) |
| Railway Redis | Included | $0 (up to 100MB) |
| Vercel (frontend) | Hobby | $0 (free tier) |
| Cloudflare R2 (storage) | Free tier | $0 (up to 10GB/mo) |
| Solana devnet | Free | $0 |
| **Total** | | **~$5-20/mo** |

---

## Troubleshooting

### Railway build fails

- Check that `packages/backend/Dockerfile` builds locally: `cd packages/backend && docker build -t rawl-backend .`
- Ensure `pyproject.toml` has all dependencies
- stable-retro needs `cmake` + `build-essential` (already in Dockerfile)

### Frontend can't reach backend

- Check CORS_ORIGINS includes your Vercel URL
- Check NEXT_PUBLIC_API_URL points to Railway backend with `/api` suffix
- Railway domains use HTTPS — make sure URLs start with `https://`

### Solana RPC errors

- Devnet can be slow or rate-limited during peak times
- Consider using a dedicated RPC provider (Helius, Alchemy, QuickNode) for production
- For staging, the free `api.devnet.solana.com` is fine

### WebSocket not connecting

- Railway supports WebSocket connections by default
- Ensure the frontend WebSocket URL matches the Railway domain
- Check that `wss://` is used (not `ws://`) for HTTPS domains

### Oracle keypair issues

- The oracle keypair must be available to the backend at runtime
- Verify `ORACLE_KEYPAIR_PATH` points to the correct file
- For staging, consider the env var approach (Option A above)
