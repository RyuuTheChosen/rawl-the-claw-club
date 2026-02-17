# Rawl Platform — Solana Smart Contracts

**Program Location:** `packages/contracts/programs/rawl/src/`
**Framework:** Anchor 0.30.1
**Rust Edition:** 2021
**Build Toolchain:** Solana platform-tools v1.52 (Rust 1.88.0)

---

## Deployments

| Network | Program ID | Status |
|---------|-----------|--------|
| **Devnet** | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` | Deployed 2026-02-17 |
| **Localnet** | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` | Same keypair |
| **Mainnet** | — | Not yet deployed |

### Devnet Addresses

| Account | Address | Description |
|---------|---------|-------------|
| Program | `AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K` | BPF program binary |
| PlatformConfig PDA | `CvKx2cxZBYwUUqjFE73s5KggNntgQth5yAWhSLDuPTUj` | Global config (bump 255) |
| Oracle | `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4` | Lock/resolve/cancel signer |
| Authority | `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4` | Platform admin (same as oracle for dev) |
| Treasury | `AEghDwMwM3XZjE5DqZyey2jJr6XvUssXVXpGsucREhm4` | Fee collection (same as oracle for dev) |
| Deployer (upgrade auth) | `HUssQyZHW2jRuAG6qeuvcDu93w5TYZfDecsSwVwyjAjd` | Can upgrade the program |

**PlatformConfig parameters:**
- Fee: 300 BPS (3%)
- Match timeout: 1800s (30 min)
- Paused: false

**Explorer:** https://explorer.solana.com/address/AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K?cluster=devnet

### Keypair Locations

| Keypair | Path | Purpose |
|---------|------|---------|
| Program | `packages/contracts/target/deploy/rawl-keypair.json` | Program ID derivation |
| Oracle | `oracle-keypair.json` (repo root) | Transaction signing (gitignored) |
| Deployer | WSL2 `~/.config/solana/id.json` | Deployment + upgrade authority |

---

## Overview

The Rawl smart contracts manage the on-chain betting system: creating match pools, accepting bets, resolving matches, distributing payouts, and handling cancellations. The platform uses a parimutuel betting model where all bets go into a shared pool, and winners split the pool proportionally after a 3% platform fee.

---

## State Accounts

### PlatformConfig

Seeds: `["platform_config"]`

| Field | Type | Description |
|-------|------|-------------|
| `authority` | Pubkey | Platform admin (can update config, pause) |
| `oracle` | Pubkey | Backend keypair authorized to lock/resolve/cancel |
| `fee_bps` | u16 | Platform fee in basis points (default 300 = 3%) |
| `treasury` | Pubkey | Fee collection wallet |
| `paused` | bool | Emergency pause flag |
| `match_timeout` | i64 | Seconds before match can be timed out (default 1800) |
| `bump` | u8 | PDA bump seed |

### MatchPool

Seeds: `["match_pool", match_id]`

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | [u8; 32] | Unique match identifier (UUID bytes) |
| `fighter_a` | Pubkey | Fighter A public key |
| `fighter_b` | Pubkey | Fighter B public key |
| `side_a_total` | u64 | Total lamports bet on side A |
| `side_b_total` | u64 | Total lamports bet on side B |
| `side_a_bet_count` | u32 | Number of bets on side A |
| `side_b_bet_count` | u32 | Number of bets on side B |
| `winning_bet_count` | u32 | Number of winning bets claimed |
| `bet_count` | u32 | Total number of bets placed |
| `status` | MatchStatus | Open, Locked, Resolved, Cancelled |
| `winner` | MatchWinner | None, SideA, SideB |
| `oracle` | Pubkey | Oracle that created this match |
| `creator` | Pubkey | Wallet that created this match |
| `created_at` | i64 | Unix timestamp |
| `lock_timestamp` | i64 | When match was locked |
| `resolve_timestamp` | i64 | When match was resolved |
| `cancel_timestamp` | i64 | When match was cancelled |
| `min_bet` | u64 | Minimum bet amount in lamports |
| `betting_window` | i64 | Seconds after creation that bets are accepted |
| `bump` | u8 | PDA bump seed |
| `vault_bump` | u8 | Vault PDA bump seed |

### Bet

Seeds: `["bet", match_id, bettor]`

| Field | Type | Description |
|-------|------|-------------|
| `bettor` | Pubkey | Wallet that placed the bet |
| `match_id` | [u8; 32] | Match identifier |
| `side` | BetSide | SideA or SideB |
| `amount` | u64 | Bet amount in lamports |
| `claimed` | bool | Whether payout has been claimed |
| `bump` | u8 | PDA bump seed |

### Vault

Seeds: `["vault", match_id]`

System account holding the SOL pool for a match. No custom data structure.

---

## Instructions

### Platform Management

| Instruction | Signer | Description |
|-------------|--------|-------------|
| `initialize` | Authority | Create PlatformConfig with fee, timeout, oracle, treasury |
| `update_fee` | Authority | Change platform fee (max 1000 bps = 10%) |
| `update_authority` | Authority | Transfer platform authority to new wallet |
| `pause` | Authority | Emergency pause all operations |
| `unpause` | Authority | Resume operations |

### Match Lifecycle

| Instruction | Signer | Description |
|-------------|--------|-------------|
| `create_match` | Creator | Create MatchPool + Vault PDAs for a new match |
| `lock_match` | Oracle | Lock match (no more bets), set status to Locked |
| `resolve_match` | Oracle | Set winner (SideA/SideB), status to Resolved |
| `cancel_match` | Oracle | Cancel match, status to Cancelled |
| `timeout_match` | Anyone | Cancel if match_timeout elapsed since lock |

### Betting

| Instruction | Signer | Description |
|-------------|--------|-------------|
| `place_bet` | Bettor | Place bet on SideA/SideB, transfer SOL to vault |
| `claim_payout` | Bettor | Claim winnings from resolved match |
| `refund_bet` | Bettor | Refund bet from cancelled match |

### Cleanup

| Instruction | Signer | Description |
|-------------|--------|-------------|
| `close_bet` | Bettor | Close Bet PDA, reclaim rent (after claim/refund) |
| `close_match` | Creator | Close MatchPool + Vault PDAs, reclaim rent |
| `withdraw_fees` | Authority | Withdraw accumulated fees from treasury |
| `sweep_unclaimed` | Authority | Sweep unclaimed payouts after claim window (30 days) |
| `sweep_cancelled` | Authority | Sweep unclaimed refunds after claim window |

---

## Betting Mechanics

### Placing a Bet

Validations:
1. Match status must be `Open`
2. Amount must be > 0
3. Amount must be >= `min_bet` (if set)
4. Current time must be <= `created_at + betting_window` (if set)

SOL is transferred from bettor to vault via CPI to System Program.

### Payout Calculation

```
pool_total = side_a_total + side_b_total
fee = pool_total * fee_bps / 10000
net_pool = pool_total - fee
payout = (bet_amount / winning_side_total) * net_pool
```

Example with 3% fee:
- Side A total: 5 SOL, Side B total: 3 SOL
- Pool: 8 SOL, Fee: 0.24 SOL, Net: 7.76 SOL
- Side A wins:
  - Bettor with 1 SOL on A: payout = (1/5) * 7.76 = 1.552 SOL
  - Bettor with 2 SOL on A: payout = (2/5) * 7.76 = 3.104 SOL

### Refund (Cancelled Match)

Full refund of original bet amount from vault to bettor. No fee deducted.

---

## Error Codes

| Code | Message | Trigger |
|------|---------|---------|
| `Unauthorized` | Only platform authority | Non-authority calls authority-only instruction |
| `OracleUnauthorized` | Only oracle | Non-oracle calls oracle-only instruction |
| `InvalidMatchStatus` | Wrong status | Instruction expects different match status |
| `MatchNotOpen` | Not open for betting | Bet on non-Open match |
| `MatchNotLocked` | Not locked | Resolve non-Locked match |
| `MatchNotResolved` | Not resolved | Claim from non-Resolved match |
| `MatchNotCancelled` | Not cancelled | Refund from non-Cancelled match |
| `ZeroBetAmount` | Amount = 0 | Bet with zero lamports |
| `BetBelowMinimum` | Below min_bet | Bet amount < min_bet |
| `BettingWindowClosed` | Window expired | Bet after betting_window elapsed |
| `BetOnLosingSide` | Wrong side | Claim from losing side |
| `AlreadyClaimed` | Double claim | Claim already-claimed bet |
| `TimeoutNotElapsed` | Too early | Timeout before match_timeout elapsed |
| `ClaimWindowNotElapsed` | Too early | Sweep before 30 days |
| `OutstandingBets` | Bets remain | Close match with unclaimed bets |
| `OutstandingWinningBets` | Winners remain | Fee withdrawal before all claims |
| `Overflow` | Arithmetic overflow | Addition overflow (safety check) |
| `InvalidFeeBps` | Fee > 10% | Set fee above MAX_FEE_BPS |
| `InvalidSide` | Bad side value | Side not 0 or 1 |
| `PlatformPaused` | Platform paused | Operation during emergency pause |
| `BetCountNotZero` | Bets exist | Close match with existing bets |
| `WinningBetCountNotZero` | Winners exist | Fee withdrawal with unclaimed winners |

---

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PLATFORM_CONFIG_SEED` | `"platform_config"` | PDA seed |
| `MATCH_POOL_SEED` | `"match_pool"` | PDA seed |
| `BET_SEED` | `"bet"` | PDA seed |
| `VAULT_SEED` | `"vault"` | PDA seed |
| `DEFAULT_FEE_BPS` | 300 | 3% platform fee |
| `MAX_FEE_BPS` | 1000 | 10% maximum fee |
| `DEFAULT_TIMEOUT_SECONDS` | 1800 | 30 minutes |
| `CLAIM_WINDOW_SECONDS` | 2,592,000 | 30 days |
| `DEFAULT_MIN_BET_LAMPORTS` | 10,000,000 | 0.01 SOL |
| `DEFAULT_BETTING_WINDOW_SECONDS` | 300 | 5 minutes |

---

## Backend Integration

The backend interacts with the contracts through:

1. **`solana/pda.py`** — Derives PDA addresses matching contract seeds
2. **`solana/instructions.py`** — Builds instructions with correct Anchor discriminators
3. **`solana/client.py`** — Signs and submits transactions via oracle keypair
4. **`solana/deserialize.py`** — Deserializes on-chain account data
5. **`solana/account_listener.py`** — WebSocket subscription for state changes
6. **`engine/oracle_client.py`** — High-level lock/resolve/cancel operations

---

## Build & Deploy

### Build (WSL2 only)

stable-retro and Solana tools do not run on native Windows. All contract builds must use WSL2.

```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.cargo/bin:$HOME/.local/share/solana/install/active_release/bin:$PATH"
  cd /mnt/c/Projects/Rawl/packages/contracts

  # Install platform-tools v1.52 (only needed once)
  cargo-build-sbf --install-only --tools-version v1.52 --force-tools-install

  # Build
  cargo-build-sbf --tools-version v1.52 \
    --manifest-path programs/rawl/Cargo.toml \
    --sbf-out-dir target/deploy
'
```

Output: `packages/contracts/target/deploy/rawl.so` (375KB)

> **Why v1.52?** The `constant_time_eq` crate requires Cargo 1.85+. platform-tools v1.51 ships Cargo 1.84 which is too old.

### Deploy to Devnet

```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url https://api.devnet.solana.com

  # Ensure deployer has >= 3 SOL
  solana balance

  solana program deploy \
    /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl.so \
    --program-id /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl-keypair.json

  # Reset to local after deploy
  solana config set --url http://127.0.0.1:8899
'
```

### Deploy to Localnet

```bash
# Start test validator (separate terminal)
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  rm -rf /tmp/rawl-test-ledger
  solana-test-validator --reset --ledger /tmp/rawl-test-ledger
'

# Deploy
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana program deploy \
    /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl.so \
    --program-id /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl-keypair.json
'
```

### Initialize PlatformConfig

After deployment (any network), initialize the global config:

```bash
cd /c/Projects/Rawl

# For devnet:
SOLANA_RPC_URL=https://api.devnet.solana.com \
SOLANA_WS_URL=wss://api.devnet.solana.com \
PROGRAM_ID=AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K \
python scripts/init-platform.py

# For localnet:
python scripts/init-platform.py
```

### Upgrade Program

The deployer wallet (`HUssQyZHW2jRuAG6qeuvcDu93w5TYZfDecsSwVwyjAjd`) holds upgrade authority. To upgrade after code changes:

```bash
# 1. Rebuild (see Build section above)
# 2. Deploy with --program-id flag (same keypair = same address, upgrades in-place)
wsl -d Ubuntu-22.04 -- bash -c '
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  solana config set --url https://api.devnet.solana.com
  solana program deploy \
    /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl.so \
    --program-id /mnt/c/Projects/Rawl/packages/contracts/target/deploy/rawl-keypair.json
  solana config set --url http://127.0.0.1:8899
'
```

> **Note:** State accounts (PlatformConfig, MatchPool, Bet) are NOT affected by program upgrades. Only the program logic changes. PlatformConfig does NOT need to be re-initialized after an upgrade.

---

## Testing

```bash
cd packages/contracts

# Build
anchor build

# Run tests (requires solana-test-validator or uses Anchor's built-in)
anchor test
```

### Test Coverage

14 tests covering:
- Platform config initialization, fee updates, fee validation, pause/unpause
- Match creation, bet placement, zero bet rejection
- Match locking, bet rejection on locked match
- Match resolution, payout claiming, double-claim rejection
- Match cancellation, bet refunds
- Oracle authorization, authority authorization

---

## PDA Derivation Reference

For backend/frontend integration, PDAs are derived as follows:

```python
# Python (backend — packages/backend/src/rawl/solana/pda.py)
from solders.pubkey import Pubkey

PROGRAM_ID = Pubkey.from_string("AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K")

# PlatformConfig
platform_config, bump = Pubkey.find_program_address([b"platform_config"], PROGRAM_ID)

# MatchPool (match_id = 32 bytes from UUID)
match_pool, bump = Pubkey.find_program_address([b"match_pool", match_id_bytes], PROGRAM_ID)

# Vault
vault, bump = Pubkey.find_program_address([b"vault", match_id_bytes], PROGRAM_ID)

# Bet
bet, bump = Pubkey.find_program_address([b"bet", match_id_bytes, bettor_pubkey.bytes], PROGRAM_ID)
```

```typescript
// TypeScript (frontend — packages/frontend/src/lib/solana.ts)
import { PublicKey } from "@solana/web3.js";

const PROGRAM_ID = new PublicKey("AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K");

// match_id: UUID string → 16 hex bytes + 16 zero bytes = 32 bytes
function matchIdToBytes(uuid: string): Uint8Array {
  const hex = uuid.replace(/-/g, "");
  const bytes = new Uint8Array(32);
  for (let i = 0; i < 16; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
}

const [matchPool] = PublicKey.findProgramAddressSync(
  [Buffer.from("match_pool"), matchIdToBytes(matchUuid)],
  PROGRAM_ID
);
```
