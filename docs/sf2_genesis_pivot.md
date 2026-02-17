# SF2 Genesis Pivot

**Date:** 2026-02-16

Migrated the emulation backend from Street Fighter III: 3rd Strike (Dreamcast/Flycast) to Street Fighter II: Special Champion Edition (Genesis) running on stable-retro 0.9.9.

---

## Motivation

- stable-retro's SF2 Genesis integration is built-in and verified working in WSL2
- No custom data.json, no BIOS files, no RetroArch needed
- SF3 Dreamcast (Flycast) required custom integration work that was incomplete

---

## What Changed

### 1. Config (`packages/backend/src/rawl/config.py`)

| Setting | Before | After |
|---------|--------|-------|
| `retro_game` | `StreetFighter3rdStrike-Dreamcast-v0` | `StreetFighterIISpecialChampionEdition-Genesis-v0` |

`retro_integration_path` remains empty — SF2 Genesis uses built-in integration.

### 2. RetroEngine (`packages/backend/src/rawl/engine/emulation/retro_engine.py`)

**Action space:** Changed from `retro.Actions.MULTI_DISCRETE` to `retro.Actions.FILTERED`. MULTI_DISCRETE has a bug in 2-player mode on Genesis. FILTERED gives `MultiBinary(24)` (12 buttons x 2 players).

**`_translate_info()`:** Rewritten to handle two naming conventions:

| SF2 Genesis (new default) | Prefixed (backward compat) |
|--------------------------|---------------------------|
| `health` -> `P1.health` | `p1_health` -> `P1.health` |
| `enemy_health` -> `P2.health` | `p2_health` -> `P2.health` |
| `matches_won` -> `P1.round_wins` | `p1_round_wins` -> `P1.round_wins` |
| `enemy_matches_won` -> `P2.round_wins` | `p2_round_wins` -> `P2.round_wins` |
| `continuetimer` -> `timer` | `time` -> `timer` |

Detection logic: if `health` AND `enemy_health` are both present in the raw info dict, the SF2 branch is used. Otherwise falls through to the prefixed branch.

**`_integration_path()`:** Simplified. Returns `None` for built-in games (no custom integration directory needed). Only returns a path if `retro_integration_path` is explicitly configured.

### 3. SF2CE Adapter (`packages/backend/src/rawl/game_adapters/sf2ce.py`) — NEW

| Property | Value |
|----------|-------|
| `game_id` | `sf2ce` |
| `MAX_HEALTH` | `176` |
| `required_fields` | `["health", "round_wins"]` |
| Round detection | Delta-based (stateful) |

**Round detection uses `matches_won` delta tracking**, not health checks. This was a critical design decision driven by real emulator behavior (see Findings below). The adapter tracks `_prev_p1_wins` and `_prev_p2_wins` and only fires when either counter increases.

`is_match_over()` uses standard best-of-N logic from `round_history` (same as sfiii3n).

### 4. Adapter Registry (`packages/backend/src/rawl/game_adapters/__init__.py`)

Added `"sf2ce": SF2CEAdapter` to `_ADAPTER_REGISTRY`. The sfiii3n adapter remains registered for future use.

### 5. Health Check (`packages/backend/src/rawl/monitoring/health_checks.py`)

Changed `import retro` to `import stable_retro` in `check_retro()`. The `retro` import still works (it's an alias) but `stable_retro` is the canonical module name.

### 6. Tests

**Updated:** `tests/test_engine/test_retro_engine.py`
- All mock info dicts use SF2 format (`health`/`enemy_health`/`continuetimer`)
- Mock action space uses `FILTERED` instead of `MULTI_DISCRETE`
- Adapter compatibility tests use `SF2CEAdapter` instead of `SFIII3NAdapter`
- Added backward-compat tests for prefixed format
- Frame sizes updated from 480x640 to 200x256 (actual Genesis output)

**New:** `tests/test_game_adapters/test_sf2ce.py`
- Validation, extract_state, is_round_over (delta-based), is_match_over
- Tests for duplicate detection suppression and transition frame handling

All existing `test_sfiii3n.py` tests continue to pass unchanged.

---

## Findings from Real Emulator (WSL2)

Running the actual SF2 Genesis ROM in stable-retro revealed behaviors not documented anywhere:

### `env.reset()` returns empty info `{}`

The initial reset produces no game state variables. Data only appears after the first `env.step()`. Our `_translate_info()` defaults handle this correctly (health=0, round_wins=0).

### `continuetimer` is NOT the round timer

Despite the name, `continuetimer` is the post-loss continue countdown (10-9-8... when you lose). During normal gameplay it is **always 0**. The actual round timer visible on screen is not exposed by stable-retro's built-in SF2 Genesis integration.

This means timer-based round-over detection (checking `timer <= 0`) would falsely trigger on every frame.

### Health stays at -1 during round transitions

After a KO, the losing player's health drops to -1 and stays there for approximately 600 frames (~10 seconds) during the victory animation and round transition. Health-based round detection (`if health <= 0: round over`) would fire hundreds of times for the same round.

### `matches_won` / `enemy_matches_won` are round wins

Despite the name "matches_won", these track round wins within a single match (best-of-3 in SF2). They increment exactly once when a round is won and remain stable until the next round ends.

### Solution: delta-based round detection

Instead of checking health or timer each frame, the SF2CE adapter watches for changes in `matches_won`/`enemy_matches_won`. This fires exactly once per round, avoids transition-frame duplicates, and doesn't depend on the missing round timer.

### Verified info dict keys

```
health           int    P1 health (0-176, can go to -1 on KO)
enemy_health     int    P2 health (0-176, can go to -1 on KO)
matches_won      int    P1 round wins within current match
enemy_matches_won int   P2 round wins within current match
continuetimer    int    Continue countdown (always 0 during gameplay)
score            int    Score counter
```

### Performance

- Frame size: 200x256x3 (RGB)
- Action space: MultiBinary(24) — 12 buttons x 2 players
- Throughput: ~2500 FPS with random actions on WSL2
- Full bo3 match: ~6300 frames (~1.7 minutes of game time at 60fps)

---

## WSL2 Smoke Test Results

Full end-to-end test: RetroEngine._translate_info() + SF2CEAdapter against the real emulator with random actions:

```
Round 1 @ frame 1785: P1 wins (76.1% hp remaining)
Round 2 @ frame 4484: P2 wins (55.1% hp remaining)
Round 3 @ frame 6319: P1 wins (81.8% hp remaining)
MATCH OVER: P1 wins 2-1

Frames: 6319 | Time: 2.5s | 2538 FPS
```

Delta-based round detection: exactly 1 detection per round, zero false positives.

---

## Files Changed

```
Modified:
  packages/backend/src/rawl/config.py
  packages/backend/src/rawl/engine/emulation/retro_engine.py
  packages/backend/src/rawl/game_adapters/__init__.py
  packages/backend/src/rawl/monitoring/health_checks.py
  packages/backend/tests/test_engine/test_retro_engine.py

New:
  packages/backend/src/rawl/game_adapters/sf2ce.py
  packages/backend/tests/test_game_adapters/test_sf2ce.py
```

---

## What's NOT Changed

- **sfiii3n adapter** — remains in registry, tests still pass, available for future SF3 integration
- **match_runner.py** — no changes needed; the adapter interface is unchanged
- **Frontend** — `sf2ce` added to `GameId` type and leaderboard game tabs (2026-02-18)
- **Solana contracts** — game-agnostic, no changes needed
- **Training pipeline** — game-agnostic, no changes needed
