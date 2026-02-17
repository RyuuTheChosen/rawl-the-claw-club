# Replace DIAMBRA with stable-retro

> **STATUS: SUPERSEDED (2026-02-16)** — This plan originally targeted SF3 3rd Strike on Dreamcast (Flycast core). That approach was abandoned because:
> - SF3 Dreamcast is not a built-in stable-retro game (requires custom integration)
> - Missing RAM addresses for `round_wins`, `stage_side`, `combo_count` — never found
> - Flycast core not bundled with stable-retro
> - Required BIOS files and 288 MB `.chd` ROM
> - 2P save state never created
>
> **Current approach:** SF2 Special Champion Edition (Genesis) — verified working 2026-02-16.
> All emulation details are now in `docs/DIAMBRA_Pipeline_Reference.md`.
> This file is kept for historical reference only (CPS3 RAM maps, Dreamcast addresses, etc.).

## Context
DIAMBRA Arena requires active account credentials and authenticates against their servers at runtime. Every match and training job has a hard dependency on DIAMBRA's infrastructure — if their auth server goes down or they revoke access, the platform goes down. For a wagering platform with real money in escrow, this is unacceptable.

We replace DIAMBRA with **stable-retro** (Farama-Foundation fork of OpenAI Gym Retro) using the **Flycast core** running the **Dreamcast version of SF3: 3rd Strike** (`StreetFighter3rdStrike-Dreamcast-v0`). This integration already exists in stable-retro's stable dataset. Open source, no credentials, no network calls, Gymnasium-compatible.

**Single launch title**: SF3: 3rd Strike (Dreamcast). No kof98, no tektagt at launch.

**Training is off-platform**: Users rent their own GPUs and run an open-source training package. The platform only handles match execution — no training worker needed in the backend.

## Architecture

```
stable-retro (Flycast core, Dreamcast SF3 ROM)
        |
  RetroEngine             ← translates obs/action/info formats
  (~100 lines)               from retro flat style to DIAMBRA nested style
        |
  match_runner.py          ← same start()/step()/stop() interface
```

No subprocess management, no Docker-in-Docker, no gRPC, no TCP sockets, no Lua plugins. The Flycast libretro core runs in-process. Match execution is a single Python process per Celery worker.

**Constraint**: stable-retro allows only one emulator per process. Celery workers already run as separate processes, so concurrent matches work naturally — one match per worker process.

## Existing Integration Status

`StreetFighter3rdStrike-Dreamcast-v0` already ships with stable-retro but is minimal:

| What exists | What's missing |
|-------------|----------------|
| `p1_health` address (`\|u1` at 0x0CE52EC0) | `p1_round_wins` / `p2_round_wins` |
| `p2_health` address (`\|u1` at 0x0CE52EC8) | `p1_stage_side` (facing direction) |
| `time` address (`\|u1` at 0x0CE4A209) | `p1_combo_count` / `p2_combo_count` |
| `scenario.json` (round-end detection) | 2P VS mode save state |
| `AlexVsChunLi.Arcade.state` (1P arcade) | `default_player_state` for 2P |
| Flycast core config (11 buttons, 640x480) | Super gauge, stun bar (nice-to-have) |

We extend this integration by adding the missing RAM variables and creating a 2P VS mode save state.

## Flycast Core Details

- **Native resolution**: 640x480 (4:3, 59.94fps NTSC)
- **ROM format**: `.chd2` or `.cdi` (Dreamcast disc image)
- **ROM SHA1**: `61af1b3779d816052bf751c59dece03dfcf9c5f2`
- **BIOS required**: `dc_boot.bin` + `dc_flash.bin` in Flycast system directory
- **RAM base**: `0x0C000000` (Dreamcast main RAM, 16MB)
- **Buttons per player**: 11 (A, B, X, Y, START, DPAD x4, L, R)
- **SF3 button mapping**: A=LK, B=LP, X=MK, Y=MP, L=HK, R=HP
- **Action space (2P, MultiDiscrete)**: `[3, 3, 8] * 2` = 72 actions per player
- **Action space (2P, MultiBinary)**: `MultiBinary(22)` (11 buttons * 2 players)
- **Characters**: 20 selectable (Alex, Ryu, Ken, Chun-Li, Yun, Yang, Dudley, Necro, Hugo, Ibuki, Elena, Oro, Sean, Urien, Makoto, Q, Twelve, Remy, Gouki/Akuma, Gill)

## SF3 Game Data

### MAX_HEALTH = 160 (not 176)

The current `sfiii3n.py` adapter has `MAX_HEALTH = 176` which is **incorrect**. Every source confirms the correct value is **160 (0xA0)**:
- DIAMBRA docs: health range `[-1, 160]`
- All CPS3/Dreamcast cheat codes set max to `0xA0`
- Grouflon's 3rd_training_lua: formats health as `"%d/160"`
- GameFAQs Damage Data FAQ: 160 points depletes a full bar

Health is identical between CPS3 arcade and Dreamcast port. Both use 160.

### CPS3 Arcade RAM Map (Reference)

Complete RAM map from [Grouflon/3rd_training_lua](https://github.com/Grouflon/3rd_training_lua) — the definitive community resource (~100+ addresses). These are CPS3 addresses, **not directly usable on Dreamcast**, but document the game's memory structure for finding Dreamcast equivalents.

**Player object structure (CPS3):**
```
P1 base: 0x02068C6C    P2 base: 0x02069104    (gap = 0x498 / 1176 bytes)

Offsets from base:
  +0x9F   health/life (u8, max 160 / 0xA0)
  +0x64   position X (s16)
  +0x68   position Y (s16)
  +0x0A   facing direction / flip_x (s8)
  +0x3C0  character ID (u16)
  +0xAC   current action (u32)
  +0xAD   movement type (u8)
  +0x202  animation ID (u16)
  +0x20E  posture (u8: 0x00=standing, 0x20=crouching, 0x16=neutral jump, etc.)
  +0x297  standing state (u8)
  +0x187  recovery time (u8)
  +0x189  hit count (u8)
  +0x428  is attacking (u8)
  +0x3D3  blocking ID (u8)
  +0x3CF  is being thrown (u8)
  +0x45   freeze frames / hitstop (u8)
  +0x43A  damage bonus (u16)
  +0x43E  stun bonus (u16)
  +0x440  defense bonus (u16)
```

**Global addresses (CPS3):**
```
0x02011377  round timer (u8, 99 = 0x63)
0x02011383  P1 round wins (u8)
0x02011385  P2 round wins (u8)
0x02011387  P1 character select ID (u8)
0x02011388  P2 character select ID (u8)
0x02011389  fighting status (u8)
0x0201138B  P1 selected Super Art (u8, 0-2)
0x0201138C  P2 selected Super Art (u8, 0-2)
0x020154A7  match state (u8, 0x02 = round active)
0x02007F00  frame number (u32)
```

**Meter/stun/combo (CPS3):**
```
0x020695B5  P1 super gauge (u8)
0x020695E1  P2 super gauge (u8)
0x020695BF  P1 meter count (u8, number of filled bars)
0x020695EB  P2 meter count (u8)
0x020695FD  P1 stun bar (u32)
0x02069611  P2 stun bar (u32)
0x020696C5  P1 combo counter (u8)
0x0206961D  P2 combo counter (u8)
```

### Dreamcast Known Addresses

**Flycast emulator addresses** (from existing stable-retro integration, RAM base 0x0C000000):
```
0x0CE52EC0  P1 health (|u1, max 160)     offset from base: 0x00E52EC0
0x0CE52EC8  P2 health (|u1, max 160)     offset from base: 0x00E52EC8
0x0CE4A209  timer (|u1, counts down)     offset from base: 0x00E4A209
```

**Dreamcast CodeBreaker addresses** (raw DC memory, different mapping than Flycast):
```
0x01EB2942  P1 health (max 0xA0 = 160)
0x01EB2DAE  P2 health (gap = 0x046C / 1132 bytes)
0x01E51E68  timer (0x6301 = infinite)
0x01EB31DE  P1 stun (never stunned = 0x00)
0x01EB31DA  P1 stun recovery
0x01EB31F2  P2 stun (never stunned = 0x00)
0x01EB31EC  P2 stun recovery
0x01B6FDEE  character select timer
0x01B3242A  enable Gill (P1)
0x01B324DC  enable Gill (P2)
```

Note: CodeBreaker and Flycast use different address mappings. The CodeBreaker addresses cannot be used directly in `data.json` — they need translation to Flycast's memory space.

### Dreamcast vs CPS3 Differences

- **Health/damage**: Identical (160 max)
- **Input buffer**: DC has ~62 move buffer vs ~127 on CPS3 — some tight combos differ
- **Version base**: DC based on CPS3 revision 990608 (later than competitive standard 990512)
- **Loading**: DC adds ~3 seconds between rounds (CPS3 is instant)
- **Player struct size**: DC ~1132 bytes vs CPS3 1176 bytes — recompiled for SH-4 CPU, similar but not identical layout

## Format Translation

RetroEngine translates between stable-retro and DIAMBRA formats so match_runner and game adapters see no change.

### Observations
```
DIAMBRA:       obs["P1"] -> (256,256,3)     obs["P2"] -> (256,256,3)
stable-retro:  obs -> (480,640,3) single shared screen

Translation:   Resize 640x480 to 256x256, serve as both obs["P1"] and obs["P2"]
               (fighting games show both characters on the same screen)
               Models consume 128x128 grayscale anyway via preprocess_for_inference()
```

### Actions
```
DIAMBRA:       {"P1": multi_discrete_array, "P2": multi_discrete_array}
stable-retro:  flat concatenated array — MultiBinary(22) or MultiDiscrete([3,3,8,3,3,8])

Translation:   RetroEngine.step() accepts {"P1": ..., "P2": ...} dict,
               concatenates into flat array for retro env
```

### Info Dict
```
DIAMBRA:       info["P1"]["health"], info["P2"]["health"], info["round"], info["timer"]
stable-retro:  info["p1_health"], info["p2_health"], info["p1_round_wins"], info["time"]  (flat)

Translation:   RetroEngine re-nests flat keys into DIAMBRA format:
               {"P1": {"health": ..., "stage_side": ..., "combo_count": ...},
                "P2": {"health": ..., ...},
                "round": ..., "timer": ...}
               Mappings: "time" → "timer", "p1_round_wins" → info["round"]
```

## Required RAM Variables

These must be in `data.json` for the sfiii3n adapter to work:

| Variable           | Status      | Flycast Address | Type   | Notes |
|--------------------|-------------|-----------------|--------|-------|
| `p1_health`        | EXISTS      | 0x0CE52EC0      | `\|u1` | Max 160, verified working |
| `p2_health`        | EXISTS      | 0x0CE52EC8      | `\|u1` | Max 160, verified working |
| `time`             | EXISTS      | 0x0CE4A209      | `\|u1` | Counts down from 99, maps to adapter "timer" |
| `p1_round_wins`    | NEEDS FIND  | TBD             | `\|u1` | CPS3 equivalent: 0x02011383. Maps to adapter "round" |
| `p2_round_wins`    | NEEDS FIND  | TBD             | `\|u1` | CPS3 equivalent: 0x02011385 |
| `p1_stage_side`    | NEEDS FIND  | TBD             | `\|i1` | CPS3: base+0x0A (facing direction, signed) |
| `p1_combo_count`   | NICE-TO-HAVE| TBD             | `\|u1` | CPS3: 0x020696C5. Not critical for match logic |
| `p2_combo_count`   | NICE-TO-HAVE| TBD             | `\|u1` | CPS3: 0x0206961D |
| `fighting_status`  | NICE-TO-HAVE| TBD             | `\|u1` | CPS3: 0x02011389. Goes to 0 between rounds — cleaner round transition signal than health-based detection. Global variable (near round_wins on CPS3). |

**Minimum viable**: `p1_health`, `p2_health`, `time`, `p1_round_wins`, `p2_round_wins`. These 5 are enough for the sfiii3n adapter to detect round/match completion. `stage_side`, `combo_count`, and `fighting_status` populate MatchState or improve detection quality but aren't required for win/loss logic — can default to 0 if not found.

**Note on CPS3 address clusters**: On CPS3, `round_wins` (0x02011383/85), `fighting_status` (0x02011389), and `timer` (0x02011377) are all in the same 0x020113xx region — they're global game state variables stored together. On Dreamcast, these will likely also be clustered near each other (but at a different base). Finding one may help locate the others.

## Finding Missing Addresses

### Strategy
The CPS3 and Dreamcast versions share the same game logic recompiled for different CPUs (Hitachi SH-2 vs SH-4). The data structures are similar but at different absolute addresses. The approach:

1. **Round wins** — On CPS3, these are global variables (not in the player struct). Search Dreamcast RAM for a byte that:
   - Starts at 0 when a match begins
   - Increments to 1 when a player wins a round
   - Increments to 2 when they win again (best of 3)
   - Resets to 0 on new match

2. **Facing direction** — On CPS3, this is at player_base + 0x0A (signed byte). The Dreamcast player struct starts somewhere near the health address. Since health is at base + 0x9F on CPS3, the DC base would be approximately `0x0CE52EC0 - 0x9F = 0x0CE52E21`. Search around `0x0CE52E2B` (base + 0x0A) for a signed byte that flips when characters cross over.

3. **Combo counter** — On CPS3, this is at a separate address (0x020696C5), not in the player struct. Search for a byte that increments with each hit in a combo and resets to 0 between combos.

### Tools
1. **stable-retro Integration UI**: `python -m stable_retro.ui` — interactive memory search with value tracking
2. **RetroArch + Flycast cheat search**: Built-in RAM search while playing
3. **Direct RAM dump**: `env.get_ram()` returns all memory as numpy array — can diff between frames to find changing values
4. **Cheat Engine + Flycast standalone**: Attach to Flycast process for memory scanning (Windows)

### Fallback
If `stage_side` and `combo_count` can't be found:
- Default `stage_side` to 0 in MatchState (doesn't affect round/match logic)
- Default `combo_count` to 0 (doesn't affect round/match logic)
- Only `round_wins` is critical for match completion detection

If `round_wins` can't be found:
- Derive round transitions from health resets (both healths jump to 160 = new round started)
- Count round wins in RetroEngine based on who had more health when a reset occurs

## New Files

```
packages/backend/src/rawl/engine/emulation/
    __init__.py
    base.py                    # EmulationEngine ABC
    retro_engine.py            # RetroEngine: wraps stable-retro, translates formats
    integrations/
        sf3_dreamcast/
            data.json          # Extended RAM addresses (existing 3 + found addresses)
            scenario.json      # Reward/done conditions
            metadata.json      # Flycast system, 1P + 2P default states
            AlexVsChunLi.Arcade.state    # Ships with stable-retro (1P)
            VsMode.2P.state              # Created manually (2P VS mode)
```

## Implementation Steps

### Step 1: Validate existing integration
- `pip install stable-retro`
- Import ROM: `python -m stable_retro.import ./roms/`
- Ensure Dreamcast BIOS files (`dc_boot.bin`, `dc_flash.bin`) are in Flycast system dir
- Verify `retro.make("StreetFighter3rdStrike-Dreamcast-v0")` loads
- Confirm `p1_health`, `p2_health`, `time` appear in `info` dict after `env.step()`
- Verify health max is 160 (play a round, confirm starting value)
- Measure native obs shape (expected 480x640x3)
- Test `players=2` with the existing Arcade state

### Step 2: Find missing RAM addresses
- Use `python -m stable_retro.ui` or RetroArch cheat search to locate:
  - `p1_round_wins` — search for byte that increments on round win
  - `p2_round_wins` — same pattern
  - `p1_stage_side` — search near estimated player base for facing byte
  - `p1_combo_count` / `p2_combo_count` — search for hit counter (nice-to-have)
- Use CPS3 address map as structural reference (offsets, not absolute addresses)
- Create extended `data.json` with all found variables
- Verify values change correctly during gameplay

### Step 3: Create 2P VS mode save state
- Launch SF3 in stable-retro with `render_mode="human"`
- Navigate: Main Menu → VS Mode → Character Select → Start Match
- Save state at round start via `env.em.get_state()` → write to `.state` file
- Update `metadata.json`:
  ```json
  {
    "default_state": "AlexVsChunLi.Arcade",
    "default_player_state": [
      "AlexVsChunLi.Arcade",
      "VsMode.2P"
    ]
  }
  ```
- Verify: `retro.make(..., players=2)` loads the 2P state and both players can input

### Step 4: Fix sfiii3n adapter MAX_HEALTH
- Change `MAX_HEALTH = 176` → `MAX_HEALTH = 160` in `game_adapters/sfiii3n.py`
- This is a confirmed bug regardless of the DIAMBRA→retro migration

### Step 5: EmulationEngine ABC (`emulation/base.py`)
- `EmulationEngine` ABC with `start()->(obs,info)`, `step(action)->(obs,r,t,t,info)`, `stop()`
- Enables testing with mock engines, future engine swaps

### Step 6: RetroEngine (`emulation/retro_engine.py`)
- ~100 lines, same interface as DiambraManager
- **Constructor**: `RetroEngine(game_id, match_id)` — stores config
- **start()**: Registers custom integration path, calls `retro.make("StreetFighter3rdStrike-Dreamcast-v0", players=2, use_restricted_actions=retro.Actions.MULTI_DISCRETE, render_mode="rgb_array")`, `env.reset()`, translates output
- **step(action)**: Translates `{"P1": a, "P2": b}` → flat array, calls `env.step()`, translates back
- **stop()**: Calls `env.close()`

```python
def _translate_obs(self, raw_obs):
    """Resize 640x480 to 256x256, wrap in P1/P2 dict."""
    resized = cv2.resize(raw_obs, (256, 256))
    return {"P1": resized, "P2": resized}

def _translate_info(self, raw_info):
    """Re-nest flat retro info into DIAMBRA-style nested dict."""
    info = {"P1": {}, "P2": {}}
    for key, val in raw_info.items():
        if key.startswith("p1_"):
            info["P1"][key[3:]] = val
        elif key.startswith("p2_"):
            info["P2"][key[3:]] = val
        elif key == "time":
            info["timer"] = val             # retro "time" → adapter "timer"
        else:
            info[key] = val                 # other globals stay top-level
    # Map round_wins to "round" for adapter compatibility
    # Adapter reads info["round"] for round number
    # We use max(p1_wins, p2_wins) * 2 - 1 + current_round as approximation,
    # or just expose round_wins and let adapter use it
    return info

def _translate_action(self, action_dict):
    """Convert {"P1": array, "P2": array} to flat concatenated array."""
    return np.concatenate([action_dict["P1"], action_dict["P2"]])
```

### Step 7: Update `config.py`
- Replace `diambra_*` settings with:
  ```python
  # Emulation (stable-retro)
  retro_game: str = "StreetFighter3rdStrike-Dreamcast-v0"
  retro_integration_path: str = ""   # Custom integration dir (auto-detected if empty)
  retro_obs_size: int = 256          # Resize target for streaming
  ```

### Step 8: Update `match_runner.py` (~5 line changes)
- Line 9: `from rawl.engine.emulation.retro_engine import RetroEngine`
- Line 54: `engine = RetroEngine(game_id, match_id)`
- Rename `diambra` variable to `engine` on lines 71, 102, 246
- Everything else unchanged — same `start()/step()/stop()` interface

### Step 9: Update `health_checks.py`
- Replace `check_diambra()` with `check_retro()`:
  ```python
  async def check_retro() -> HealthStatus:
      """Check that stable-retro is importable and ROM is available."""
      start = time.monotonic()
      try:
          import stable_retro
          rom_path = stable_retro.data.get_romfile_path(settings.retro_game)
          return HealthStatus(
              "retro", True,
              latency_ms=(time.monotonic() - start) * 1000,
              message=f"ROM found: {settings.retro_game}",
          )
      except FileNotFoundError:
          return HealthStatus("retro", False, message=f"ROM not found: {settings.retro_game}")
      except Exception as e:
          return HealthStatus("retro", False, message=str(e))
  ```
- Update `get_all_health()`: `check_diambra` → `check_retro`

### Step 10: Gut `training/worker.py`
- Training is off-platform now
- Remove `import diambra.arena` and the DIAMBRA env creation code
- Mark training pipeline with `NotImplementedError` pointing to the external training package

### Step 11: Cleanup
- Delete `engine/diambra_manager.py`
- Update `game_adapters/base.py` docstring: "DIAMBRA env info dicts" → "emulation engine info dicts"
- Remove `diambra` from dependencies
- Add `stable-retro` and `opencv-python-headless` to dependencies

### Step 12: Tests
- Unit tests for RetroEngine with mocked `retro.make()`
- Format translation tests:
  - flat→nested info (including `time`→`timer` mapping, `round_wins` handling)
  - dict→flat action concatenation
  - obs resize from 640x480→256x256
- Integration test: load SF3 Dreamcast integration, verify all info fields present
- Verify translated info passes `SFIII3NAdapter.validate_info()` with no errors

### Step 13: Docker
- Worker Dockerfile: `pip install stable-retro opencv-python-headless`
- Dreamcast BIOS files copied into image system directory
- ROM file (`.chd2` or `.cdi`) mounted or copied: `-v ./roms:/app/roms`
- Custom integrations dir copied into image
- ROM import step in entrypoint: `python -m stable_retro.import /app/roms/`
- No MAME binary, no Lua, no Docker-in-Docker, no gRPC

## Key Design Decisions

**Single shared screen**: Both AI fighters see the same 640x480 frame, resized to 256x256. Models consume 128x128 grayscale via `preprocess_for_inference()`. No separate per-player views needed for fighting games.

**Format translation in RetroEngine**: Adapters stay untouched. RetroEngine re-nests stable-retro's flat info dict into the existing DIAMBRA format. The engine is swappable — if a better emulation option appears later, only `retro_engine.py` changes.

**One emulator per process**: stable-retro enforces this (`gc.collect()` before creating a new `RetroEmulator`). Celery's prefork worker pool already gives us one process per worker. Each match gets its own worker process with its own RetroEngine instance. `celery worker --concurrency=4` runs 4 matches in parallel across 4 processes.

**CPU-only inference**: The policy networks are small 3-layer CNNs. Inference takes <1ms on CPU. Two inferences + one emulator step per frame fits well within the 16.67ms budget at 60fps. No GPU needed for match execution.

**Training off-platform**: The platform publishes an open-source pip-installable training package containing the stable-retro env wrapper, observation preprocessing, and default PPO config. Users rent their own GPU time and submit trained checkpoints via `POST /api/gateway/submit`. The platform validates checkpoints in a sandboxed container before marking them match-ready.

**Action space**: Using `Actions.MULTI_DISCRETE` which gives `[3, 3, 8]` per player (3 vertical directions, 3 horizontal directions, 8 button combos including none/A/B/X/Y/L/R/START). The training package will document the exact action space so submitted models are compatible.

**Macro actions for training** (off-platform training package concern, not match engine): The hijkzzz/mame-street-fighter-3-ai project found that macro actions were critical for reaching difficulty 7. Frame-by-frame quarter-circle inputs (↓↘→+P for Hadouken) are nearly impossible for RL to discover through random exploration. The training package should provide an optional `MacroActionWrapper` that maps single discrete actions to multi-frame input sequences (e.g., action 15 = Hadouken, action 16 = Shoryuken). This doesn't affect the match engine — RetroEngine always receives raw button presses. But the training package needs macro support documented. hijkzzz used 34 macros covering specials, supers, and combo starters.

**Character ID table** (same across CPS3 and Dreamcast):
```
0=Gill  1=Alex  2=Ryu  3=Yun  4=Dudley  5=Necro  6=Hugo  7=Ibuki
8=Elena  9=Oro  10=Yang  11=Ken  12=Sean  13=Urien  14=Gouki/Akuma
15=Gill(dup)  16=Chun-Li  17=Makoto  18=Q  19=Twelve  20=Remy
```

## Files Modified
- `packages/backend/src/rawl/config.py` — retro settings replace DIAMBRA settings
- `packages/backend/src/rawl/engine/match_runner.py` — ~5 line import/instantiation swap
- `packages/backend/src/rawl/training/worker.py` — gut DIAMBRA code, mark as off-platform
- `packages/backend/src/rawl/monitoring/health_checks.py` — check_retro() replaces check_diambra()
- `packages/backend/src/rawl/game_adapters/base.py` — docstring only
- `packages/backend/src/rawl/game_adapters/sfiii3n.py` — fix MAX_HEALTH 176→160
- `pyproject.toml` — remove diambra, add stable-retro + opencv-python-headless

## Files Created
- `packages/backend/src/rawl/engine/emulation/__init__.py`
- `packages/backend/src/rawl/engine/emulation/base.py`
- `packages/backend/src/rawl/engine/emulation/retro_engine.py`
- `packages/backend/src/rawl/engine/emulation/integrations/sf3_dreamcast/data.json`
- `packages/backend/src/rawl/engine/emulation/integrations/sf3_dreamcast/scenario.json`
- `packages/backend/src/rawl/engine/emulation/integrations/sf3_dreamcast/metadata.json`
- `packages/backend/src/rawl/engine/emulation/integrations/sf3_dreamcast/VsMode.2P.state`

## Files Deleted
- `packages/backend/src/rawl/engine/diambra_manager.py`

## Risk: RAM Address Discovery

3-5 required RAM addresses are missing from the Dreamcast Flycast memory space. The CPS3 addresses are fully documented but can't be used directly — different CPU architecture means different absolute addresses.

**What we know:**
- Health addresses confirmed working (0x0CE52EC0 / 0x0CE52EC8, 8 bytes apart)
- Timer address confirmed working (0x0CE4A209)
- CPS3 player struct is 1176 bytes; Dreamcast is ~1132 bytes (similar but recompiled)
- CPS3 has round_wins as global variables (not in player struct)
- CodeBreaker raw DC addresses exist for health/stun but use different mapping than Flycast

**Search strategy:**
1. Round wins — search for byte starting at 0, incrementing on round win
2. Facing — search near `health_addr - 0x95` for signed byte that flips on crossover
3. Combo counter — search for byte matching on-screen combo count
4. Use `env.get_ram()` to dump full RAM, diff between frames to find candidates

**Fallback (if addresses not found):**
- `stage_side`: default to 0 (not used in win/loss logic)
- `combo_count`: default to 0 (not used in win/loss logic)
- `round_wins`: derive from health resets — when both healths jump to 160, a new round started. Track who had more health at the transition to determine round winner. This is reliable for best-of-3/5 detection.

## Community Resources

- [Grouflon/3rd_training_lua](https://github.com/Grouflon/3rd_training_lua) — definitive CPS3 RAM map (~100+ addresses)
- [M-J-Murray/MAMEToolkit](https://github.com/M-J-Murray/MAMEToolkit) — CPS3 RL environment (5 addresses)
- [peon2/fbneo-training-mode](https://github.com/peon2/fbneo-training-mode) — FBNeo training mode
- [FBNeo-cheats/sfiii3.ini](https://github.com/finalburnneo/FBNeo-cheats) — FBNeo cheat database
- [DIAMBRA sfiii3n docs](https://docs.diambra.ai/v2.1/envs/games/sfiii3n/) — complete observation space reference
- [Almar's Guides](https://www.almarsguides.com/retro/walkthroughs/Dreamcast/Games/StreetFighterIII3rdStrike/CodeBreaker/) — Dreamcast CodeBreaker addresses
- [GameFAQs Damage FAQ](https://gamefaqs.gamespot.com/dreamcast/913699-street-fighter-iii-3rd-strike/faqs/29359) — damage data confirming MAX_HEALTH=160

## Verification Checklist
1. `pip install stable-retro` — installs cleanly
2. `retro.make("StreetFighter3rdStrike-Dreamcast-v0")` — loads with ROM + BIOS
3. `env.step()` returns `info` with `p1_health` (max 160), `p2_health`, `time`
4. Extended `data.json` with found variables loads without errors
5. 2P VS mode save state loads and both players accept input
6. `RetroEngine.start()` returns translated `(obs, info)` matching DIAMBRA format
7. `SFIII3NAdapter.validate_info(translated_info)` — passes (with MAX_HEALTH=160)
8. Full match loop: start → step N frames → round over → match over → stop
9. `ruff check src/` — no new lint errors
