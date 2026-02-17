# Rawl Platform — API Reference

**Base URL:** `http://localhost:8080`

---

## Public API

No authentication required. Rate limited per IP via Redis sliding window counters.

**Rate Limits:**

| Endpoint | Limit | Window |
|----------|-------|--------|
| `GET /api/matches` | 60 requests | 60 seconds |
| `GET /api/fighters` | 30 requests | 60 seconds |
| `GET /api/leaderboard` | 30 requests | 60 seconds |
| `GET /api/odds` | 120 requests | 60 seconds |

Exceeding a limit returns HTTP 429 with a `Retry-After` header. If Redis is unavailable, requests are allowed (graceful degradation).

### Matches

#### `GET /api/matches`

List matches with cursor-based pagination.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | - | Base64 pagination cursor |
| `limit` | int | 20 | Items per page (1-100) |
| `status` | string | - | Filter: `upcoming` (→open), `live` (→locked), `completed` (→resolved), `all` |
| `game` | string | - | Filter by game ID |
| `type` | string | - | Filter: `ranked`, `challenge`, `exhibition`, `all` |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "game_id": "sf2ce",
      "match_format": 3,
      "fighter_a_id": "uuid",
      "fighter_b_id": "uuid",
      "winner_id": "uuid | null",
      "status": "open | locked | resolved | cancelled",
      "match_type": "ranked | challenge | exhibition",
      "has_pool": true,
      "side_a_total": 500000000,
      "side_b_total": 300000000,
      "created_at": "2026-02-15T10:00:00Z",
      "locked_at": "2026-02-15T10:01:00Z | null",
      "resolved_at": "2026-02-15T10:05:00Z | null"
    }
  ],
  "next_cursor": "base64string | null",
  "has_more": true
}
```

#### `GET /api/matches/{match_id}`

Get match details.

---

### Fighters

#### `GET /api/fighters`

List fighters (ready status only, ordered by Elo).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game_id` | string | - | Filter by game |
| `cursor` | string | - | Pagination cursor |
| `limit` | int | 20 | Items per page |

#### `GET /api/fighters/{fighter_id}`

Get fighter details.

**Response:**
```json
{
  "id": "uuid",
  "name": "ShadowKen",
  "game_id": "sf2ce",
  "character": "Ken",
  "elo_rating": 1450.0,
  "matches_played": 42,
  "wins": 28,
  "losses": 14,
  "status": "ready",
  "division_tier": "Gold",
  "created_at": "2026-01-15T10:00:00Z"
}
```

---

### Odds

#### `GET /api/odds/{match_id}`

Get current betting odds for a match.

**Response:**
```json
{
  "match_id": "uuid",
  "side_a_total": 500000000,
  "side_b_total": 300000000,
  "odds_a": 1.6,
  "odds_b": 2.67,
  "pool_total": 800000000
}
```

---

### Bets

#### `GET /api/bets`

List bets for a wallet.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `wallet` | string | **required** | Wallet address (max 44 chars) |
| `match_id` | uuid | - | Filter by match |
| `status` | string | - | Filter by bet status |

**Response:**
```json
[
  {
    "id": "uuid",
    "match_id": "uuid",
    "wallet_address": "7xKXtg...",
    "side": "a",
    "amount_sol": 1.5,
    "status": "confirmed | claimed | refunded",
    "created_at": "2026-02-15T10:00:00Z"
  }
]
```

#### `POST /api/matches/{match_id}/bets`

Record a bet after on-chain transaction succeeds.

**Request:**
```json
{
  "wallet_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
  "side": "a",
  "amount_sol": 1.5,
  "tx_signature": "base58_transaction_signature"
}
```

**Validations:**
- Match must exist and have `open` status
- One bet per wallet per match (409 if duplicate)
- `side` must be `"a"` or `"b"`
- `wallet_address` max 44 characters

**Response (201):**
```json
{
  "id": "uuid",
  "match_id": "uuid",
  "wallet_address": "7xKXtg...",
  "side": "a",
  "amount_sol": 1.5,
  "status": "confirmed",
  "created_at": "2026-02-15T10:00:00Z"
}
```

---

### Leaderboard

#### `GET /api/leaderboard/{game_id}`

Get ranked fighter leaderboard.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Number of entries |

**Response:**
```json
[
  {
    "rank": 1,
    "fighter_id": "uuid",
    "fighter_name": "ShadowKen",
    "owner_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "elo_rating": 1650.0,
    "wins": 45,
    "losses": 5,
    "matches_played": 50,
    "division": "Diamond"
  }
]
```

---

### Internal

#### `GET /api/health`

System health check.

**Response:**
```json
{
  "status": "healthy | degraded",
  "components": [
    {
      "component": "database",
      "healthy": true,
      "latency_ms": 2.5,
      "message": null
    },
    {
      "component": "redis",
      "healthy": true,
      "latency_ms": 0.8,
      "message": null
    }
  ]
}
```

#### `GET /api/metrics`

Prometheus metrics in exposition format.

---

### Pretrained Models

#### `GET /api/pretrained`

List available pretrained baseline models.

**Response:**
```json
[
  {
    "id": "sf2ce-linyilyi-2500k",
    "game_id": "sf2ce",
    "name": "linyiLYi SF2 Baseline (2.5M steps)",
    "s3_key": "pretrained/sf2ce-linyilyi-2500k.zip"
  },
  {
    "id": "sf2ce-thuongmhh-discrete15",
    "game_id": "sf2ce",
    "name": "thuongmhh SF2 Discrete-15",
    "s3_key": "pretrained/sf2ce-thuongmhh-discrete15.zip"
  }
]
```

---

## Gateway API (Authenticated)

Requires `X-Api-Key` header. Obtain key via `/api/gateway/register`.

### Registration

#### `POST /api/gateway/register`

Register a wallet and receive an API key.

**Request:**
```json
{
  "wallet_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
  "signature": "base58_ed25519_signature",
  "message": "Sign this message to register with Rawl: <nonce>"
}
```

**Response:**
```json
{
  "api_key": "rawl_xxxxxxxxxxxx",
  "wallet_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
}
```

---

### Fighter Submission

#### `POST /api/gateway/submit`

Submit a trained fighter model for validation.

**Rate limit:** 3 submissions per wallet per hour. Returns HTTP 429 with `Retry-After` header.

**Request:**
```json
{
  "name": "ShadowKen",
  "game_id": "sf2ce",
  "character": "Ken",
  "model_s3_key": "models/user123/shadowken_v1.zip"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "ShadowKen",
  "game_id": "sf2ce",
  "character": "Ken",
  "elo_rating": 1000.0,
  "matches_played": 0,
  "wins": 0,
  "losses": 0,
  "status": "validating",
  "created_at": "2026-02-15T10:00:00Z"
}
```

---

### Training

> **Note:** Training is **off-platform**. Users rent their own GPUs and run the open-source `rawl-trainer` package locally. The platform handles model validation and match execution only. The training endpoints below exist in the API but dispatch to a stub that raises `NotImplementedError`. They are retained for future on-platform training support.

#### `POST /api/gateway/train`

Start a training job for a fighter. *(Currently returns NotImplementedError — training is off-platform.)*

**Request:**
```json
{
  "fighter_id": "uuid",
  "algorithm": "PPO",
  "total_timesteps": 1000000,
  "tier": "free | standard | pro"
}
```

**Response (501):** `NotImplementedError` — use the external `rawl-trainer` package instead.

#### `GET /api/gateway/train/{job_id}`

Get training job status.

#### `POST /api/gateway/train/{job_id}/stop`

Stop a running or queued training job.

---

### Matchmaking

#### `POST /api/gateway/queue`

Queue a fighter for Elo-proximity matchmaking.

**Request:**
```json
{
  "fighter_id": "uuid",
  "game_id": "sf2ce",
  "match_type": "ranked"
}
```

**Response:**
```json
{
  "queued": true,
  "message": "Fighter queued for matchmaking"
}
```

**Matching algorithm:**
- Redis sorted set keyed by game_id, score = Elo rating
- Candidates within +/-200 Elo are paired
- Window widens by 50 Elo per 10s scheduler tick
- Self-matching prohibited (different owner_id required)

#### `POST /api/gateway/match`

Create a custom match (pick your opponent).

**Request:**
```json
{
  "fighter_a_id": "uuid",
  "fighter_b_id": "uuid",
  "match_format": 3,
  "has_pool": false
}
```

**Validations:**
- Fighter A must be owned by the caller
- Fighter B must exist and be in `ready` status
- Both fighters must be from the same game
- Self-matching prohibited (different owners)

**Response (201):**
```json
{
  "match_id": "uuid",
  "game_id": "sf2ce",
  "status": "pending"
}
```

---

### My Fighters

#### `GET /api/gateway/fighters`

List the authenticated user's fighters.

**Response:** Array of fighter objects (same schema as public fighters, includes all statuses).

#### `GET /api/gateway/fighters/{fighter_id}`

Get a specific fighter owned by the authenticated user. Returns 404 if not owned.

#### `POST /api/gateway/fighters/{fighter_id}/recalibrate`

Re-run calibration for a fighter that previously failed.

**Validations:**
- Fighter must be owned by the caller
- Fighter status must be `calibration_failed` (returns 400 otherwise)

**Response:**
```json
{
  "message": "Recalibration started",
  "fighter_id": "uuid"
}
```

---

## WebSocket Endpoints

### Video Stream

**`ws://{host}/ws/matches/{match_id}/video`**

Binary JPEG frames at ~30fps. Max 2 connections per IP.

### Data Stream

**`ws://{host}/ws/matches/{match_id}/data`**

JSON messages at 10Hz. Max 5 connections per IP.

```json
{
  "match_id": "uuid",
  "timestamp": "2026-02-15T10:02:15.123Z",
  "health_a": 150,
  "health_b": 120,
  "round": 2,
  "timer": 85,
  "status": "fighting",
  "round_winner": null,
  "match_winner": null,
  "team_health_a": null,
  "team_health_b": null,
  "active_char_a": null,
  "active_char_b": null,
  "odds_a": 1.6,
  "odds_b": 2.67,
  "pool_total": 800000000
}
```

### Training Progress

**`ws://{host}/ws/gateway/train/{job_id}`**

JSON messages every ~10K timesteps.

```json
{
  "job_id": "uuid",
  "current_timesteps": 250000,
  "total_timesteps": 1000000,
  "reward": 1.25
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (validation error, business rule violation) |
| 401 | Unauthorized (missing/invalid API key, user not found) |
| 404 | Resource not found |
| 429 | Rate limit exceeded (includes `Retry-After` header) |
| 500 | Internal server error |

---

## Pagination

All list endpoints use cursor-based pagination with base64-encoded `(created_at, id)` cursors.

```
GET /api/matches?limit=20
-> { items: [...], next_cursor: "eyJ...", has_more: true }

GET /api/matches?limit=20&cursor=eyJ...
-> { items: [...], next_cursor: "eyJ...", has_more: true }

GET /api/matches?limit=20&cursor=eyJ...
-> { items: [...], next_cursor: null, has_more: false }
```
