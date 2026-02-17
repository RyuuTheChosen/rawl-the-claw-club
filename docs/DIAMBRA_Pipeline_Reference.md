# Emulation Pipeline Reference (stable-retro / Genesis)

**Technical reference for Rawl's match execution emulation layer**

> **Updated 2026-02-16:** Emulation verified working with **Street Fighter II Special Champion Edition (Genesis)** running on stable-retro 0.9.9 in WSL2. Previous references to SF3 Dreamcast / Flycast were unverified and have been replaced.

---

## 1. Architecture

```
Celery Worker Process (WSL2)
        |
  RetroEngine          <- translates obs/action/info formats
  (~150 lines)            from retro flat style to adapter nested style
        |
  stable-retro         <- Gymnasium-compatible env wrapping genesis_plus_gx core
        |
  Genesis Plus GX      <- libretro core emulating Sega Genesis / Mega Drive
        |
  ROM File (.md)       <- SF2: Special Champion Edition (U) [!]
```

**Single process, no network calls.** The genesis_plus_gx libretro core runs in-process. No Docker containers, no gRPC, no authentication servers, no RetroArch.

**One emulator per process** — stable-retro enforces this. Celery's prefork worker pool gives one process per worker. `celery worker --concurrency=4` runs 4 matches in parallel across 4 OS processes.

**WSL2 required** — stable-retro does not build on native Windows. All emulation runs inside WSL2 (Ubuntu-22.04).

**Repository:** https://github.com/Farama-Foundation/stable-retro

---

## 2. Installation

stable-retro must be installed in **WSL2**, not native Windows.

```bash
# Inside WSL2
wsl -d Ubuntu-22.04

pip3 install stable-retro Pillow

# Copy ROM to stable-retro data directory
# Source: "Street Fighter II' - Special Champion Edition (U) [!].bin"
# Destination: rom.md in the game's data dir
cp "/path/to/rom.bin" \
  /usr/local/lib/python3.10/dist-packages/stable_retro/data/stable/StreetFighterIISpecialChampionEdition-Genesis-v0/rom.md

# Verify
python3 -c "
import os; os.environ['SDL_VIDEODRIVER'] = 'dummy'
import stable_retro
env = stable_retro.make('StreetFighterIISpecialChampionEdition-Genesis-v0', render_mode='rgb_array')
obs, info = env.reset()
print('OK — obs shape:', obs.shape)
env.close()
"
```

**Prerequisites:**
- WSL2 with Ubuntu-22.04
- Python 3.10+ (3.10 tested in WSL2)
- `stable-retro==0.9.9`
- SF2 Special Champion Edition ROM (`.bin` renamed to `.md`)
- No BIOS required (Genesis does not need BIOS files)

**ROM Details:**
- File: `Street Fighter II' - Special Champion Edition (U) [!].bin`
- SHA1: `a5aad1d108046d9388e33247610dafb4c6516e0b`
- Size: 3,145,728 bytes (3 MB)
- Rename to `rom.md` and place in stable-retro data directory

---

## 3. Game Environment

### Creating an Environment

```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"  # No display in WSL2
import stable_retro

env = stable_retro.make(
    "StreetFighterIISpecialChampionEdition-Genesis-v0",
    players=2,
    use_restricted_actions=stable_retro.Actions.FILTERED,
    render_mode="rgb_array",
    inttype=stable_retro.data.Integrations.ALL,
)
obs, info = env.reset()
```

> **Important:** Use `Actions.FILTERED`, not `Actions.MULTI_DISCRETE`. The MULTI_DISCRETE mode has a bug with 2-player Genesis games (`IndexError: list index out of range`).

### Observation Space

| Property | Value |
|----------|-------|
| Shape | `(200, 256, 3)` — cropped single shared screen |
| Dtype | `uint8` (0-255 RGB) |
| Frame rate | ~60 fps (NTSC Genesis) |

RetroEngine resizes to `retro_obs_size` (default 256x256) and wraps as `{"P1": array, "P2": array}` for adapter compatibility. Models consume 84x84 grayscale (DeepMind WarpFrame standard) via `preprocess_for_inference()`, with 4-frame stacking yielding a final observation shape of `(84, 84, 4)`.

### Action Space

**MultiBinary(24):** 12 buttons x 2 players (with `Actions.FILTERED`).

**Button mapping (Genesis 6-button):**

| Button | SF2 Action |
|--------|-----------|
| B | Light Punch |
| A | Light Kick |
| C | Medium Punch |
| Y | Medium Kick |
| X | Heavy Punch |
| Z | Heavy Kick |
| MODE | — |
| START | Start/Pause |
| UP/DOWN/LEFT/RIGHT | D-pad |

**Characters (12):** Ryu, Ken, Chun-Li, Guile, Blanka, Dhalsim, Zangief, Honda, Balrog, Vega, Sagat, M. Bison

### Info Dict (RAM Variables)

stable-retro exposes these from the built-in `data.json`:

| Key | Type | Address | Description |
|-----|------|---------|-------------|
| `health` | `>i2` | `16744514` | P1 health (max 176) |
| `enemy_health` | `>i2` | `16745154` | P2 health (max 176) |
| `matches_won` | `\|u1` | `16744922` | P1 rounds won |
| `enemy_matches_won` | `>u4` | `16745559` | P2 rounds won |
| `continuetimer` | `\|u1` | `16744917` | Continue countdown timer |
| `score` | `>d4` | `16744936` | P1 score |

**All variables are built-in** — no custom `data.json` or RAM address discovery required. This is a major advantage over the SF3 Dreamcast approach, which had missing RAM addresses for `round_wins`, `stage_side`, and `combo_count`.

### Scenario (Round End Detection)

The built-in `scenario.json` uses `continuetimer == 10` as the done condition.

---

## 4. RetroEngine Translation Layer

RetroEngine (`engine/emulation/retro_engine.py`) translates between stable-retro's flat format and the nested dict format expected by game adapters.

### Observations

```
stable-retro:  obs -> (200, 256, 3) single shared screen
RetroEngine:   obs -> {"P1": (256, 256, 3), "P2": (256, 256, 3)}  (resized)
```

### Actions

```
Adapter format:  {"P1": array(12), "P2": array(12)}
stable-retro:    array(24)  (flat concatenated, MultiBinary)
```

### Info Dict

```
stable-retro:  {"health": 176, "enemy_health": 80, "matches_won": 1, "continuetimer": 0, "score": 50000}
RetroEngine:   {"P1": {"health": 176, "stage_side": 0, "combo_count": 0, "round_wins": 1},
                "P2": {"health": 80, "stage_side": 0, "combo_count": 0, "round_wins": 0},
                "timer": 0, "round": 2}
```

Note: The translation maps `health`/`enemy_health` to `P1`/`P2` nested format, `matches_won`/`enemy_matches_won` to `round_wins`, and `continuetimer` to `timer`.

---

## 5. Integration Files

**No custom integration files needed.** SF2 Genesis ships with complete built-in integration in stable-retro:

```
stable_retro/data/stable/StreetFighterIISpecialChampionEdition-Genesis-v0/
├── rom.md                              # ROM file (user-provided)
├── rom.sha                             # Expected SHA1 hash
├── data.json                           # RAM addresses (6 variables, all present)
├── metadata.json                       # Default state reference
├── scenario.json                       # Done condition + reward
└── Champion.Level1.RyuVsGuile.state    # Default save state (2P ready)
```

The existing custom integration files at `engine/emulation/integrations/sf3_dreamcast/` are **not used** for SF2 Genesis.

---

## 6. SF2 Game Data

### Health

- **MAX_HEALTH = 176** (confirmed via stable-retro info dict: starting `health` and `enemy_health` both read 176)
- This differs from SF3 which uses MAX_HEALTH = 160

### Default State

- `Champion.Level1.RyuVsGuile` — starts directly in a fight (Ryu vs Guile, Champion Edition mode)
- Both players can input immediately — no menu navigation required
- This eliminates the need to create a custom 2P save state (which was a blocker for SF3 Dreamcast)

### Key Advantages Over SF3 Dreamcast

| Aspect | SF3 Dreamcast (old) | SF2 Genesis (current) |
|--------|--------------------|-----------------------|
| ROM format | `.chd` (288 MB) | `.bin`/`.md` (3 MB) |
| BIOS required | Yes (`dc_boot.bin`, `dc_flash.bin`) | No |
| Core | Flycast (not bundled) | genesis_plus_gx (bundled) |
| RAM variables | 3 found, 5+ missing | All 6 built-in |
| 2P save state | Needs manual creation | Built-in |
| Custom data.json | Required | Not needed |
| Action space (2P) | Untested | Verified working |
| Build on Windows | No (same) | No (same — WSL2 required) |

---

## 7. Rawl Integration

| Component | Role |
|-----------|------|
| `RetroEngine` | Wraps stable-retro, translates formats, manages lifecycle |
| `EmulationEngine` ABC | Abstract interface — `start()`, `step()`, `stop()` |
| `match_runner.py` | Calls `engine.start()`, runs game loop, calls `engine.stop()` |
| `config.py` | `retro_game`, `retro_integration_path`, `retro_obs_size` settings |
| `check_retro()` | Health check — verifies ROM is importable |
| Game Adapters | Consume translated info dict from RetroEngine |

### Config (Completed)

Settings in `config.py` are configured for SF2 Genesis:

```python
retro_game: str = "StreetFighterIISpecialChampionEdition-Genesis-v0"
retro_obs_size: int = 256
retro_integration_path: str = ""  # not needed for SF2 — built-in integration is complete
```

### Game Adapter (Completed)

The `sf2ce` game adapter (`game_adapters/sf2ce.py`) is the active launch title:
- `MAX_HEALTH = 176`
- Round detection via `matches_won` / `enemy_matches_won` delta tracking
- 12 characters
- Standard best-of-N format

### Key Design Decisions

**CPU-only inference:** Policy networks are small 3-layer CNNs. Two inferences + one emulator step per frame fits within 16.67ms at 60fps. No GPU needed for match execution.

**Training off-platform:** Users rent their own GPUs and run the open-source training package. The platform only handles match execution.

**Format translation in RetroEngine:** Adapters stay untouched. RetroEngine re-nests stable-retro's flat info dict into the format adapters expect. The engine is swappable — only `retro_engine.py` changes if a better emulation option appears.

**WSL2 as runtime:** Since stable-retro doesn't compile on native Windows, all emulation runs in WSL2. The Celery worker process that executes matches must run inside WSL2.

---

## 8. Standalone Test

To verify emulation works without the full system (no FastAPI, Celery, Docker):

```bash
wsl -d Ubuntu-22.04 -- python3 scripts/test_stable_retro.py
```

Or manually:

```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import stable_retro
import numpy as np

env = stable_retro.make(
    "StreetFighterIISpecialChampionEdition-Genesis-v0",
    players=2,
    use_restricted_actions=stable_retro.Actions.FILTERED,
    render_mode="rgb_array",
    inttype=stable_retro.data.Integrations.ALL,
)

obs, info = env.reset()
print(f"Obs: {obs.shape}, Health: {info['health']}/{info['enemy_health']}")

for _ in range(120):
    obs, reward, term, trunc, info = env.step(env.action_space.sample())

print(f"After 120 frames — P1: {info['health']}, P2: {info['enemy_health']}")
env.close()
```

Expected output: game boots, frames render at 200x256x3, health values read correctly, no errors.

---

## 9. Bundled Emulator Cores

stable-retro 0.9.9 ships with these libretro cores (no separate install needed):

| Platform | Core | Extension | File |
|----------|------|-----------|------|
| **Genesis** | genesis_plus_gx | `.md` | `genesis_plus_gx_libretro.so` |
| Atari 2600 | stella | `.a26` | `stella_libretro.so` |
| NES | fceumm | `.nes` | `fceumm_libretro.so` |
| SNES | snes9x | `.sfc` | `snes9x_libretro.so` |
| N64 | parallel_n64 | `.n64` | `parallel_n64_libretro.so` |
| Game Boy | gambatte | `.gb` | `gambatte_libretro.so` |
| GBA | mgba | `.gba` | `mgba_libretro.so` |
| Saturn | mednafen_saturn | `.chd` | `mednafen_saturn_libretro.so` |
| Arcade (FBNeo) | fbneo | `.zip` | `fbneo_libretro.so` |

Genesis is the most mature and well-tested platform in stable-retro.

---

*Last updated: February 18, 2026*
