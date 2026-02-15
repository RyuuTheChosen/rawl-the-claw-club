# Rawl Platform — API Reference

**Base URL:** `http://localhost:8000`

---

## Public API

No authentication required. Rate limited per IP.

### Matches

#### `GET /api/matches`

List matches with cursor-based pagination.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | - | Base64 pagination cursor |
| `limit` | int | 20 | Items per page (max 100) |
| `status` | string | - | Filter: `open`, `locked`, `resolved`, `cancelled` |
| `game_id` | string | - | Filter by game |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "game_id": "sfiii3n",
      "match_format": "bo3",
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
  "game_id": "sfiii3n",
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

#### `GET /api/matches/{match_id}/odds`

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

## Gateway API (Authenticated)

Requires `X-API-Key` header. Obtain key via `/gateway/register`.

### Registration

#### `POST /gateway/register`

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

#### `POST /gateway/submit`

Submit a trained fighter model for validation.

**Rate limit:** 3 submissions per wallet per hour. Returns HTTP 429 with `Retry-After` header.

**Request:**
```json
{
  "name": "ShadowKen",
  "game_id": "sfiii3n",
  "character": "Ken",
  "model_s3_key": "models/user123/shadowken_v1.zip"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "ShadowKen",
  "game_id": "sfiii3n",
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

#### `POST /gateway/train`

Start a training job for a fighter.

**Request:**
```json
{
  "fighter_id": "uuid",
  "algorithm": "PPO",
  "total_timesteps": 1000000,
  "tier": "free | standard | pro"
}
```

**Tier limits:**

| Tier | Max Timesteps | GPU | Concurrent Jobs |
|------|--------------|-----|-----------------|
| free | 500,000 | T4 | 1 |
| standard | 5,000,000 | T4 | 2 |
| pro | 50,000,000 | A10G | 4 |

**Response (201):**
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

#### `GET /gateway/train/{job_id}`

Get training job status.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "queued | running | completed | failed | cancelled",
  "current_timesteps": 250000,
  "total_timesteps": 1000000,
  "reward": 1.25,
  "error_message": null
}
```

#### `POST /gateway/train/{job_id}/stop`

Stop a running or queued training job.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "cancelled"
}
```

---

### Matchmaking

#### `POST /gateway/queue`

Queue a fighter for Elo-proximity matchmaking.

**Request:**
```json
{
  "fighter_id": "uuid",
  "game_id": "sfiii3n",
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

#### `POST /gateway/match`

Create a custom match (pick your opponent).

**Request:**
```json
{
  "fighter_a_id": "uuid",
  "fighter_b_id": "uuid",
  "match_format": "bo1 | bo3 | bo5",
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
  "game_id": "sfiii3n",
  "status": "pending"
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
