# FightBet — Software Design Document

**AI-Powered Fighting Game Arena with Solana Wagering**

| | |
|---|---|
| **Version** | 1.0.0 |
| **Date** | February 14, 2026 |
| **Status** | Draft |
| **Classification** | Confidential |

> Deep Reinforcement Learning × Competitive Gaming × Decentralized Finance

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [AI Fighting Engine](#3-ai-fighting-engine)
4. [Match Orchestration Backend](#4-match-orchestration-backend)
5. [Solana Wagering System](#5-solana-wagering-system)
6. [Spectator Frontend](#6-spectator-frontend)
7. [Data Flows](#7-data-flows)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Security and Risk Mitigation](#9-security-and-risk-mitigation)
10. [Development Roadmap](#10-development-roadmap)
11. [Appendices](#11-appendices)

---

## 1. Introduction

### 1.1 Purpose

This Software Design Document (SDD) describes the architecture, components, data flows, and interfaces for FightBet, a platform that combines deep reinforcement learning-trained fighting game AI agents with a Solana-based spectator wagering system. The document serves as the primary technical reference for development, review, and future maintenance.

### 1.2 Scope

FightBet is a full-stack platform consisting of four integrated subsystems:

- **AI Fighting Engine:** Deep RL agents trained via DIAMBRA Arena's emulation engine that compete in classic fighting games (Street Fighter III, Mortal Kombat, Tekken, etc.) in real-time 1v1 matches. DIAMBRA is used solely for ROM emulation — all competition infrastructure is custom-built.
- **Match Orchestration Backend:** A server-side system that manages match queues, runs game environments, captures frame data, and broadcasts match state to spectators.
- **Solana Wagering System:** On-chain smart contracts (programs) that manage escrow, betting pools, odds calculation, and automated payouts using SOL or SPL tokens.
- **Spectator Frontend:** A web application providing live match streaming, real-time odds, wallet integration, and betting interfaces for observers.

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|-----------|
| DRL | Deep Reinforcement Learning |
| PPO | Proximal Policy Optimization, a policy gradient RL algorithm |
| DIAMBRA | Open-source RL platform used as the game emulation engine (Docker + gRPC) |
| SB3 | Stable Baselines 3, a set of reliable RL algorithm implementations |
| SPL Token | Solana Program Library token standard |
| PDA | Program Derived Address, a deterministic Solana account address |
| Escrow | On-chain account holding wagered funds until match resolution |
| Parimutuel | Betting model where all bets are pooled and odds are determined by the pool distribution |
| Oracle | A trusted component that submits off-chain match results on-chain |
| WebSocket | Full-duplex communication protocol for real-time data streaming |

### 1.4 References

- DIAMBRA Arena Documentation: https://docs.diambra.ai
- DIAMBRA Arena GitHub: https://github.com/diambra/arena
- Stable Baselines 3 Documentation: https://stable-baselines3.readthedocs.io
- Solana Developer Documentation: https://docs.solana.com
- Anchor Framework: https://www.anchor-lang.com
- OpenAI Gymnasium API: https://gymnasium.farama.org

---

## 2. System Overview

### 2.1 Product Vision

FightBet creates a new category of entertainment by combining autonomous AI combat with decentralized betting. Trained deep RL agents fight each other in classic arcade fighting games while spectators place wagers using Solana. The platform delivers the excitement of competitive esports with the transparency and speed of blockchain-based settlement.

### 2.2 High-Level Architecture

The system follows a layered architecture with four distinct tiers that communicate through well-defined interfaces:

| Layer | Component | Technology |
|-------|-----------|-----------|
| Presentation | Spectator Frontend | React, Next.js, WebSocket Client |
| Application | Match Orchestrator | Python, FastAPI, Redis, WebSocket |
| AI Engine | DIAMBRA Engine (emulation only) + RL Agents | DIAMBRA Docker Engine, SB3, PyTorch |
| Blockchain | Wagering System | Solana, Anchor, Rust |

### 2.3 Key Design Principles

- **Modularity:** Each subsystem operates independently and communicates via defined APIs, allowing components to be upgraded or replaced without system-wide impact.
- **Trustless Settlement:** Match results are finalized on-chain via a verifiable oracle, and payouts are executed automatically by the Solana program with no manual intervention.
- **Real-Time Performance:** Match state is broadcast with sub-second latency via WebSockets, ensuring spectators see action and can place bets with current information.
- **Extensibility:** The agent registry supports pluggable models, enabling community-submitted agents and new fighting games by adding DIAMBRA-supported ROMs to the engine.

---

## 3. AI Fighting Engine

### 3.1 DIAMBRA Arena as Emulation Engine

DIAMBRA Arena is used strictly as the game emulation layer. Its Docker-based engine runs arcade ROMs and exposes them via gRPC, while its Python package (`diambra-arena`) provides a Gymnasium-compatible API for sending gamepad actions and receiving observations (screen pixels + RAM state). We do not use DIAMBRA's competition platform, agent submission system, or Twitch streaming — all competition, matchmaking, streaming, and wagering infrastructure is built in-house.

#### 3.1.0 How the Engine Works

The DIAMBRA stack has two pieces:

1. **DIAMBRA Engine** — A closed-source binary running inside a Docker container (`docker.io/diambra/engine:latest`). It emulates the arcade ROM, processes gamepad inputs frame-by-frame, reads RAM values (health bars, timer, etc.), and serves everything over a gRPC endpoint on port 50051.
2. **DIAMBRA Arena** — The open-source Python package (`pip install diambra-arena`) that connects to the Engine via gRPC and exposes the standard Gymnasium `env.reset()` / `env.step()` / `env.render()` interface.

For our platform, the Match Runner spins up Engine containers on demand (one per match), connects via gRPC, runs the game loop, and captures all output. Multiple Engine instances can run in parallel on the same host for concurrent matches.

#### 3.1.1 Supported Games (Initial Launch)

- Street Fighter III: 3rd Strike (`sfiii3n`)
- Ultimate Mortal Kombat 3 (`umk3`)
- Tekken Tag Tournament (`tektagt`)
- Dead or Alive++ (`doapp`)
- King of Fighters 98 (`kof98`)

#### 3.1.2 Environment Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| n_players | 2 | AI vs AI competitive mode |
| action_space | MultiDiscrete | Separate move + attack actions |
| frame_shape | 128x128x1 (grayscale) | Balanced quality vs compute |
| render_mode | rgb_array | Capture frames for streaming |
| splash_screen | False | Skip intros for fast matches |

### 3.2 Agent Architecture

#### 3.2.1 Observation Space

Agents receive a composite observation consisting of visual frame data and numerical RAM states:

- **Frame Stack:** 4 consecutive grayscale frames (128x128x4) providing temporal context for motion detection, attack timing, and projectile tracking.
- **RAM Features:** Normalized numerical values extracted from game memory including player health (P1 and P2), round timer, current round number, player stage side (left/right), and character-specific meters.

#### 3.2.2 Policy Network

The agent policy network uses a dual-stream architecture that processes visual and numerical inputs separately before combining them for action selection:

1. **Visual Stream:** 3-layer CNN (32, 64, 64 filters) with ReLU activations processing the 128x128x4 frame stack, outputting a 512-dimensional feature vector.
2. **RAM Stream:** 2-layer MLP (64, 64 units) processing normalized RAM features, outputting a 64-dimensional feature vector.
3. **Fusion Layer:** Concatenation of both streams followed by 2 fully connected layers (256, 128 units) with ReLU.
4. **Action Heads:** Separate output heads for move actions (9 discrete) and attack actions (game-specific, typically 10–12 discrete) following MultiDiscrete action space.

#### 3.2.3 Training Pipeline

Agents are trained using Proximal Policy Optimization (PPO) via Stable Baselines 3 with the following configuration:

| Hyperparameter | Value | Notes |
|----------------|-------|-------|
| Algorithm | PPO | Stable, parallelizable |
| Learning Rate | 3e-4 (linear decay) | Standard for PPO |
| Batch Size | 2048 | Per environment step |
| Parallel Environments | 16 | Vectorized via SubprocVecEnv |
| Total Timesteps | 50M per game | ~72 hrs on 4x GPU |
| Reward Shaping | Custom composite | HP delta + round win + combo bonus |
| Self-Play | Enabled | Both sides trained simultaneously |

#### 3.2.4 Self-Play Training

We leverage DIAMBRA's native 2-player environment mode for self-play training — this is a feature of the emulation engine, not their competition platform. A single environment instance trains both agents simultaneously. The self-play loop operates as follows:

1. Both agents share the same policy network initially.
2. After every 100K steps, the current policy is saved as a historical opponent.
3. The training agent plays 70% of matches against itself and 30% against randomly sampled historical policies to prevent strategy collapse.
4. An Elo rating system tracks agent strength across training checkpoints.

### 3.3 Agent Registry

Trained agents are versioned and stored in an Agent Registry with the following metadata:

- Model ID (UUID), game ID, character selection
- PyTorch model weights (.zip checkpoint from SB3)
- Training metadata: total timesteps, Elo rating, win rate vs baseline
- Inference requirements: GPU memory, average step latency

The registry supports both platform-trained house agents and community-submitted agents (Phase 5 feature).

---

## 4. Match Orchestration Backend

### 4.1 Overview

The Match Orchestration Backend is the central coordination layer. It manages the lifecycle of every match from scheduling through result finalization, and serves as the bridge between the AI engine, spectator frontend, and blockchain wagering system.

### 4.2 Core Components

#### 4.2.1 Match Queue Service

Manages a priority queue of pending matches. Matches can be created by the platform scheduler (automated matchmaking) or by user requests (challenge mode). Each match request specifies two agent IDs, game selection, and match format (best-of-1, best-of-3, or best-of-5). The service enforces a configurable cooldown between matches for the same agent pair to maintain variety.

#### 4.2.2 Match Runner

The Match Runner is a stateful process that executes a single match from start to finish:

1. Loads both agent models from the Agent Registry into GPU memory.
2. Instantiates the DIAMBRA 2-player environment with the specified game and characters.
3. Runs the game loop: at each frame, queries both agents for actions, steps the environment, captures the observation and reward.
4. Extracts structured match state from RAM observations on every frame: P1 health, P2 health, round number, timer, combo counter, stage side.
5. Publishes frame data and structured state to the State Broadcaster via an internal message queue.
6. On match completion, generates a signed MatchResult payload containing the winner, final scores, round history, and a deterministic match hash for verification.

#### 4.2.3 State Broadcaster

A WebSocket server that pushes real-time match data to all connected spectator clients. It operates on two channels:

- **Video Channel:** Encoded game frames (MJPEG or WebRTC) at 30fps for live visual spectating. Frames are captured from DIAMBRA render output and compressed server-side.
- **Data Channel:** JSON payloads at 10Hz containing structured match state (health bars, timer, round, combo count, current odds) for UI rendering and betting interface updates.

#### 4.2.4 Result Oracle

Upon match completion, the Result Oracle finalizes the outcome on the Solana blockchain:

1. Receives the signed MatchResult from the Match Runner.
2. Validates the result integrity (checks match hash, verifies agent IDs, confirms round scores are consistent).
3. Submits a `resolve_match` transaction to the Solana Escrow Program with the winner ID and match metadata.
4. The on-chain program verifies the oracle signature and triggers automatic payout distribution.

### 4.3 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Server | FastAPI (Python) | REST endpoints for match management |
| WebSocket Server | FastAPI WebSocket | Real-time state broadcasting |
| Message Queue | Redis Streams | Internal match state pub/sub |
| Match State Store | Redis | Ephemeral match state + history cache |
| Persistent Storage | PostgreSQL | Match history, agent registry, user data |
| Task Scheduler | Celery + Redis | Automated match scheduling |
| Video Encoding | FFmpeg / MJPEG | Frame compression for streaming |

### 4.4 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matches` | List upcoming, live, and recent matches |
| GET | `/api/matches/{id}` | Get match details, state, and result |
| POST | `/api/matches` | Create a new match (admin/scheduler) |
| GET | `/api/agents` | List registered agents with Elo ratings |
| GET | `/api/agents/{id}` | Agent details, win rate, match history |
| WS | `/ws/match/{id}` | WebSocket stream for live match data |
| GET | `/api/odds/{match_id}` | Current betting odds for a match |

---

## 5. Solana Wagering System

### 5.1 Overview

The wagering system is implemented as a Solana on-chain program (smart contract) using the Anchor framework. It employs a parimutuel betting model where all wagers for a match are pooled together, and payouts are distributed proportionally to winners after deducting a platform fee. This model eliminates the need for a traditional bookmaker and ensures the platform bears no directional risk.

### 5.2 On-Chain Program Architecture

#### 5.2.1 Account Structure

The Solana program manages the following account types:

- **MatchPool (PDA):** One per match. Stores match ID, agent A and B identifiers, pool balances for each side, match status (open, locked, resolved, cancelled), oracle public key, winner, and creation timestamp. Derived from seeds: `["match", match_id]`.
- **Bet (PDA):** One per user per match. Stores bettor public key, match ID, chosen side (A or B), wager amount in lamports, timestamp, and payout claimed flag. Derived from seeds: `["bet", match_id, bettor_pubkey]`.
- **Platform Config (PDA):** Singleton. Stores platform authority, oracle authority, fee basis points (default 300 = 3%), treasury wallet, and global pause flag. Derived from seeds: `["config"]`.
- **Vault (PDA):** Token account holding escrowed SOL/SPL tokens for active match pools. Derived from seeds: `["vault", match_id]`.

#### 5.2.2 Program Instructions

| Instruction | Description | Access Control |
|-------------|------------|----------------|
| `initialize` | Create platform config with authority and fee settings | Platform authority |
| `create_match` | Initialize MatchPool PDA and Vault for a new match | Platform authority |
| `place_bet` | Transfer SOL to vault, create Bet PDA, update pool totals | Any user (wallet) |
| `lock_match` | Freeze betting (match is starting), set status to locked | Oracle authority |
| `resolve_match` | Set winner, calculate payouts, set status to resolved | Oracle authority |
| `claim_payout` | Transfer winnings from vault to bettor based on share | Winning bettor |
| `cancel_match` | Refund all bets, close match pool | Platform authority |
| `withdraw_fees` | Transfer accumulated platform fees to treasury | Platform authority |

#### 5.2.3 Parimutuel Odds and Payout Calculation

Odds are calculated dynamically based on the current pool distribution and displayed to users in real-time:

> *Implied Odds for Side A = Total Pool / Side A Pool*

When the match resolves, each winning bettor receives a share proportional to their wager:

> *Payout = (User Bet / Winning Side Pool) × Total Pool × (1 − Fee Rate)*

**Example:** Total pool is 100 SOL (Side A: 40 SOL, Side B: 60 SOL). Side A wins. A user who bet 10 SOL on Side A receives: (10/40) × 100 × 0.97 = **24.25 SOL**. The platform retains 3 SOL as fees.

### 5.3 Match Lifecycle (On-Chain)

1. **`create_match`:** Platform backend creates the MatchPool. Status = OPEN. Betting window opens.
2. **`place_bet` (repeated):** Spectators connect wallets and place wagers. SOL is transferred to the vault. Odds update in real-time on the frontend.
3. **`lock_match`:** Oracle signals match is starting. Status = LOCKED. No further bets accepted.
4. **`resolve_match`:** Oracle submits the winner after match completion. Status = RESOLVED. Payout amounts are calculated and stored.
5. **`claim_payout` (repeated):** Each winning bettor calls claim to withdraw their share from the vault. Losing bets are not refundable.

### 5.4 Security Considerations

- **Oracle Trust:** The Result Oracle is the only account authorized to resolve matches. In v1, this is a platform-controlled keypair. Future iterations will implement a multi-sig oracle or a verifiable computation proof to decentralize trust.
- **Reentrancy Protection:** The `claim_payout` instruction uses a `claimed` flag on the Bet PDA to prevent double-claiming. Transfer happens only once per bet.
- **Overflow Protection:** All arithmetic uses checked math (Rust `checked_add`, `checked_mul`) to prevent overflow exploits in payout calculations.
- **Account Validation:** Anchor constraints verify PDA derivation, signer authority, and account ownership on every instruction to prevent unauthorized access.
- **Minimum Bet:** Enforced at 0.01 SOL to prevent dust attack spam on the program.

---

## 6. Spectator Frontend

### 6.1 Overview

The frontend is a React-based web application built with Next.js. It provides the spectator experience: watching live AI fights, viewing real-time odds, connecting Solana wallets, and placing wagers. The UI prioritizes low-latency responsiveness and an immersive viewing experience.

### 6.2 Core Views

#### 6.2.1 Arena View (Live Match)

The primary view during a live match, consisting of:

- **Game Stream:** Central viewport rendering the live game frames received over WebSocket. Displayed at native resolution with optional upscaling. Supports fullscreen mode.
- **Health Bar Overlay:** Animated health bars for Player 1 (Agent A) and Player 2 (Agent B) positioned above the game stream, updated in real-time from RAM state data.
- **Match Info Panel:** Round number, timer, current game, character names, and agent Elo ratings.
- **Betting Panel:** Displays current odds for each side, total pool size, user bet amount input, and a place bet button. Connected to the Solana program via wallet adapter.
- **Live Odds Chart:** A small time-series chart showing how odds have shifted during the betting window.

#### 6.2.2 Lobby View

Displays upcoming scheduled matches, currently live matches, and recently completed matches with results. Each match card shows the two agents, their Elo ratings, the game being played, match time, and current pool size (for upcoming matches with open betting).

#### 6.2.3 Agent Profile View

Detailed view of an individual agent showing its Elo rating, win/loss record, match history, training metadata, and a highlight reel of notable wins. Users can browse all registered agents and compare their statistics.

#### 6.2.4 User Dashboard

Authenticated view (wallet-connected) showing the user's betting history, active bets, pending payouts to claim, total profit/loss, and transaction history linked to Solana Explorer.

### 6.3 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Next.js 14 (App Router) | SSR, routing, API routes |
| UI Library | React 18 + Tailwind CSS | Component rendering + styling |
| State Management | Zustand | Lightweight global state |
| Wallet Integration | @solana/wallet-adapter | Phantom, Solflare, Backpack |
| Blockchain SDK | @coral-xyz/anchor | Interact with Solana program |
| Real-Time Data | Native WebSocket | Match stream + state updates |
| Charts | Recharts | Odds chart, user stats |

---

## 7. Data Flows

### 7.1 Match Execution Flow

The end-to-end flow for a single match proceeds through the following stages:

1. Scheduler creates a match entry in the database and calls `create_match` on the Solana program, opening the betting pool.
2. The frontend displays the upcoming match in the Lobby. Spectators connect wallets and place bets via the `place_bet` instruction.
3. At the scheduled start time, the Match Runner spins up a DIAMBRA Engine Docker container, loads both agent models into GPU memory, the Oracle calls `lock_match` on-chain to freeze betting, and the 2-player environment is instantiated via gRPC.
4. The game loop runs: each frame, both agents produce actions, the environment steps, and the State Broadcaster pushes frame + state data to all WebSocket clients.
5. The frontend Arena View renders the stream and updates health bars, timer, and odds in real-time.
6. When the match ends (all rounds complete), the Match Runner produces a signed MatchResult.
7. The Result Oracle validates and submits `resolve_match` on-chain with the winner.
8. Winning bettors call `claim_payout` from the frontend to withdraw their winnings.

### 7.2 WebSocket Message Schema

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | string | UUID of the current match |
| `timestamp` | int64 | Unix timestamp in milliseconds |
| `p1_health` | float | Player 1 health (0.0 to 1.0) |
| `p2_health` | float | Player 2 health (0.0 to 1.0) |
| `round` | int | Current round number |
| `timer` | int | Remaining round time in seconds |
| `status` | enum | `FIGHTING` \| `ROUND_END` \| `MATCH_END` |
| `odds_a` | float | Current implied odds for Agent A |
| `odds_b` | float | Current implied odds for Agent B |
| `pool_total` | float | Total pool size in SOL |
| `frame` | base64 | JPEG-encoded game frame (video channel) |

---

## 8. Deployment Architecture

### 8.1 Infrastructure

| Service | Infrastructure | Specifications |
|---------|---------------|----------------|
| DIAMBRA Engine | Docker containers on GPU VM | 1 container per match, gRPC on :50051 |
| Match Runner | GPU VM (AWS/GCP) | NVIDIA T4/A10G, 16GB VRAM, 8 vCPU |
| API + WebSocket | Kubernetes (EKS/GKE) | Auto-scaling, 2–8 pods |
| Redis | Managed Redis (ElastiCache) | r6g.large, clustered |
| PostgreSQL | Managed RDS | db.r6g.large, Multi-AZ |
| Frontend | Vercel / Cloudflare Pages | Edge-deployed, global CDN |
| Solana RPC | Helius / QuickNode | Dedicated RPC with WebSocket |

### 8.2 Solana Network Strategy

Development and testing will be conducted on Solana Devnet with airdropped SOL. The program will be audited before deployment to Mainnet-Beta. The platform will use a dedicated Helius or QuickNode RPC endpoint for reliable transaction submission and WebSocket subscriptions for on-chain event monitoring.

---

## 9. Security and Risk Mitigation

### 9.1 Threat Model

| Threat | Mitigation | Severity |
|--------|-----------|----------|
| Oracle Manipulation | Oracle key stored in HSM; multi-sig planned for v2 | Critical |
| Match Rigging | Deterministic match replay; match hash on-chain | High |
| Double Claim | PDA-level `claimed` flag; idempotent instruction | High |
| Bot Spam Betting | Minimum bet (0.01 SOL); rate limiting | Medium |
| WebSocket Injection | Server-to-client only; read-only stream | Low |
| Smart Contract Exploit | Professional audit pre-mainnet; Anchor constraints | Critical |

### 9.2 Regulatory Considerations

The platform must comply with applicable gambling regulations in each jurisdiction it operates. Geo-fencing will be implemented to restrict access from prohibited jurisdictions. Legal counsel should be engaged to determine licensing requirements before mainnet launch. The parimutuel model is preferred as it is regulated differently (and often more favorably) than fixed-odds betting in many jurisdictions.

---

## 10. Development Roadmap

| Phase | Deliverables | Duration | Dependencies |
|-------|-------------|----------|-------------|
| 1 | Train 2+ competitive agents on Street Fighter III via DIAMBRA + SB3. Validate agent quality via internal Elo benchmarks. | 2 weeks | GPU infrastructure |
| 2 | Build Match Runner, State Broadcaster (WebSocket), and REST API. Internal match execution without frontend. | 2 weeks | Phase 1 agents |
| 3 | Develop and test Solana escrow program (Anchor). Deploy to Devnet. Unit + integration tests. | 3 weeks | None (parallel) |
| 4 | Build spectator frontend: Arena view, Lobby, wallet connect, betting UI. Integrate with backend WebSocket and Solana program. | 3 weeks | Phases 2 + 3 |
| 5 | Community features: user-submitted agents, leaderboard, tournament brackets, agent marketplace. Solana mainnet deployment after audit. | Ongoing | Phase 4 + Audit |

---

## 11. Appendices

### Appendix A: DIAMBRA Engine Match Loop

Minimal code showing how the Match Runner uses DIAMBRA's emulation engine to execute a 2-player AI match:

```python
import diambra.arena

env = diambra.arena.make("sfiii3n",
    render_mode="rgb_array",
    settings={"n_players": 2}
)

obs, info = env.reset(seed=42)

while True:
    actions = {
        "P1": agent_a.predict(obs["P1"]),
        "P2": agent_b.predict(obs["P2"])
    }
    obs, reward, terminated, truncated, info = env.step(actions)
    broadcaster.send(obs, info)

    if terminated or truncated:
        break

env.close()
```

### Appendix B: Solana Program Escrow Pseudocode

```rust
#[program]
pub mod fightbet {
    pub fn create_match(ctx, match_id, agent_a, agent_b) {
        let pool = &mut ctx.accounts.match_pool;
        pool.match_id = match_id;
        pool.agent_a = agent_a;
        pool.agent_b = agent_b;
        pool.status = MatchStatus::Open;
    }

    pub fn place_bet(ctx, side, amount) {
        require!(pool.status == Open);
        require!(amount >= MIN_BET);
        transfer(bettor -> vault, amount);
        bet.side = side;
        bet.amount = amount;
        pool.side_totals[side] += amount;
    }

    pub fn resolve_match(ctx, winner) {
        require!(ctx.accounts.oracle.key == pool.oracle);
        pool.winner = winner;
        pool.status = Resolved;
    }

    pub fn claim_payout(ctx) {
        require!(!bet.claimed && bet.side == pool.winner);
        let payout = bet.amount * pool.total
            / pool.side_totals[winner] * (1 - FEE);
        transfer(vault -> bettor, payout);
        bet.claimed = true;
    }
}
```

---

*End of Document*
