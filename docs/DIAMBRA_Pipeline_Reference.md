# DIAMBRA Arena Pipeline Reference

**Technical reference for Rawl's AI Fighting Engine (TaaS)**

---

## 1. Architecture

```
Python Script  <--gRPC/Protobuf-->  Docker Container (DIAMBRA Engine)
                                          |
                                     Arcade Emulator
                                          |
                                       ROM File
```

**Two components:**

1. **DIAMBRA Engine** — Closed-source binary in Docker (`docker.io/diambra/engine:latest`). Emulates the arcade ROM, processes gamepad inputs frame-by-frame, reads RAM values (health, timer, etc.), serves everything over gRPC on port 50051.
2. **DIAMBRA Arena** — Open-source Python package (`pip install diambra-arena`). Connects to the engine via gRPC, exposes standard Gymnasium `env.reset()` / `env.step()` / `env.render()` interface.

**Repositories:**
- Arena package: https://github.com/diambra/arena
- Agent examples: https://github.com/diambra/agents
- CLI tool: https://github.com/diambra/cli (Go-based)

---

## 2. Installation

```bash
pip install diambra              # CLI tool
pip install diambra-arena        # Python package
pip install diambra-arena[stable-baselines3]  # SB3 integration (v2.1.*)

# ROM management
diambra arena list-roms
diambra arena check-roms /path/to/rom.zip
export DIAMBRAROMSPATH=/path/to/roms/
```

**Prerequisites:** Docker Desktop, Python 3.x, free diambra.ai account, valid ROM files (SHA256 verified).

---

## 3. Running Environments

### CLI-Managed (Recommended)

```bash
diambra run -r /path/to/roms python script.py          # Single environment
diambra run -s=16 -r /path/to/roms python train.py     # 16 parallel environments
diambra run -g -r /path/to/roms python script.py       # With server-side rendering (Linux)
```

The CLI:
1. Pulls the engine Docker image
2. Starts N containers (one per `-s` count), each named `arena-{ID}`
3. Maps gRPC port 50051 to dynamic host ports
4. Mounts ROMs and credentials into containers
5. Populates `DIAMBRA_ENVS` env var with space-separated endpoints
6. Executes the Python script
7. Cleans up containers on exit

### Manual Docker

```bash
docker run -d --rm --name engine \
  -v $HOME/.diambra/credentials:/tmp/.diambra/credentials \
  -v /path/to/roms:/opt/diambraArena/roms \
  -p 127.0.0.1:50051:50051 \
  docker.io/diambra/engine:latest

DIAMBRA_ENVS=localhost:50051 python script.py
```

### Arena Subcommands

```bash
diambra arena up              # Start engine container(s)
diambra arena -s=4 up         # Start 4 parallel instances
diambra arena down            # Stop all engines
diambra arena status          # Check engine status
```

### Key CLI Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--path.roms` | `-r` | `~/.diambra/roms` | ROM files directory |
| `--env.scale` | `-s` | `1` | Number of concurrent environments |
| `--env.image` | — | auto-detect | Custom engine Docker image |
| `--env.autoremove` | `-x` | `true` | Auto-remove containers on exit |
| `--engine.render` | `-g` | `false` | Server-side graphics rendering |
| `--engine.lockfps` | `-l` | `false` | Lock FPS |

---

## 4. Environment Configuration

### EnvironmentSettings (Single Player)

**Immutable (set at creation):**

| Setting | Default | Description |
|---------|---------|-------------|
| `game_id` | required | Game identifier (e.g., `"sfiii3n"`) |
| `frame_shape` | (0,0,0) | `(H, W, C)` — C=1 for grayscale, C=0 or 3 for RGB |
| `action_space` | MULTI_DISCRETE | `SpaceTypes.DISCRETE` or `SpaceTypes.MULTI_DISCRETE` |
| `n_players` | 1 | 1 or 2 |
| `step_ratio` | 6 | Game frames per env step (1–6) |
| `splash_screen` | True | Toggle splash screen |

**Episode settings (mutable at reset via `options` dict):**

| Setting | Default | Description |
|---------|---------|-------------|
| `difficulty` | None | Game-specific difficulty level |
| `continue_game` | 0.0 | Probability of continuing after game over |
| `characters` | None | Character selection (string or tuple) |
| `role` | None | `Roles.P1`, `Roles.P2`, or None (random) |
| `outfits` | 1 | Character outfit index |

### EnvironmentSettingsMultiAgent (Two Player)

Same base settings but per-player values are **tuples**:

```python
settings = EnvironmentSettingsMultiAgent()
settings.action_space = (SpaceTypes.DISCRETE, SpaceTypes.DISCRETE)
settings.characters = ("Ryu", "Ken")
settings.outfits = (2, 2)
```

---

## 5. Observation Space

`gymnasium.spaces.Dict` with global + per-player entries:

### Global

| Key | Type | Description |
|-----|------|-------------|
| `frame` | Box (H x W x C, uint8) | Screen pixels (RGB or grayscale) |
| `stage` | Box | Current stage number |
| `timer` | Box | Round time remaining |

### Per-Player (nested under `"P1"` / `"P2"`)

| Key | Type | Description |
|-----|------|-------------|
| `side` | Discrete(2) | 0=left, 1=right |
| `wins` | Box | Rounds won count |
| `character` | Discrete | Selected character index |
| `health` | Box | Health bar value (game-specific range) |

### Game-Specific RAM Values

| Game | Extra RAM Fields |
|------|-----------------|
| sfiii3n | `stun_bar` (0–72), `stunned` (binary), `super_bar` (0–128), `super_type`, `super_count` |
| kof98umh | `power_bar` (0–100), `special_attacks_count` (0–5) |
| samsh5sp | `rage_bar` (0–100), `weapon_bar` (0–120), `power_bar` (0–64), `weapon_lost` |
| umk3 | `aggressor_bar` (0–48) |
| tektagt | Dual character health tracking, reserve character health |
| mvsc / xmvsf | Dual character health, super meter, partner/tag status |

---

## 6. Action Space

### Discrete

Single integer per step: move OR attack (shared no-op). Total = `n_moves + n_attacks - 1`.

### MultiDiscrete

Two integers per step: `[move_index, attack_index]`. Simultaneous move + attack. Total = `n_moves × n_attacks`.

All games share 9 movement actions: No-Move + 8 directions.

---

## 7. Reward Function

Default: health differential per step.

```
R_t = Σ [(opponent_health_before - opponent_health_after) - (own_health_before - own_health_after)]
```

- Dealing damage = positive reward
- Taking damage = negative reward
- **2-Player mode:** Zero-sum. Agent 0 gets +R, Agent 1 gets -R.
- **Normalized reward:** Divides by `(normalization_factor × max_delta_health)` for cross-game consistency.

---

## 8. Wrappers

Configured via `WrappersSettings`, applied in order:

| Wrapper | Setting | Default | Description |
|---------|---------|---------|-------------|
| NoopReset | `no_op_max` | 0 | Random no-op actions (0–12) after reset |
| StickyActions | `repeat_action` | 1 | Repeat action for N steps (requires step_ratio=1) |
| NormalizeReward | `normalize_reward` | False | Divide reward by health range |
| ClipReward | `clip_reward` | False | Sign function: {-1, 0, +1} |
| NoAttackCombos | `no_attack_buttons_combinations` | False | Remove combined attack buttons |
| WarpFrame | `frame_shape` | — | Resize and/or grayscale conversion |
| FrameStack | `stack_frames` | 1 | Stack 1–48 frames along channel dim |
| FrameStack dilation | `dilation` | 1 | Sample every N-th frame |
| AddLastAction | `add_last_action` | False | Add previous action to observation |
| ActionsStack | `stack_actions` | 1 | Stack 1–48 recent actions |
| Scale | `scale` | False | Normalize Box to [0,1], one-hot discrete |
| ExcludeImageScaling | `exclude_image_scaling` | False | Skip frame normalization (SB3 needs this True) |
| RoleRelative | `role_relative` | False | Rename P1/P2 to own/opp |
| Flatten | `flatten` | False | Flatten nested dict (required for SB3) |
| FilterKeys | `filter_keys` | None | Keep only specified observation keys |

**FrameStack special behavior:** Resets frame buffer on round/stage/game transitions to avoid mixing frames from different game states.

---

## 9. Stable Baselines 3 Integration

### Environment Creation

```python
from diambra.arena.stable_baselines3.make_sb3_env import make_sb3_env
from diambra.arena import EnvironmentSettings, WrappersSettings, SpaceTypes

settings = EnvironmentSettings()
settings.frame_shape = (128, 128, 1)
settings.action_space = SpaceTypes.DISCRETE
settings.characters = ("Kasumi",)
settings.difficulty = 3

wrappers = WrappersSettings()
wrappers.normalize_reward = True
wrappers.no_attack_buttons_combinations = True
wrappers.stack_frames = 4
wrappers.dilation = 1
wrappers.add_last_action = True
wrappers.stack_actions = 12
wrappers.scale = True
wrappers.exclude_image_scaling = True   # SB3 normalizes pixels itself
wrappers.role_relative = True
wrappers.flatten = True                 # Required for SB3
wrappers.filter_keys = ["action", "own_health", "opp_health",
                         "own_side", "opp_side", "opp_character",
                         "stage", "timer"]

env, num_envs = make_sb3_env("doapp", settings, wrappers)
```

**SB3 constraints:**
- `exclude_image_scaling = True` — SB3 expects pixels in [0–255]
- `flatten = True` — SB3 cannot handle nested dict observations
- Use `MultiInputPolicy` for dict observation spaces

### Training

```python
from stable_baselines3 import PPO
from diambra.arena.stable_baselines3.utils import linear_schedule, AutoSave

agent = PPO("MultiInputPolicy", env,
    gamma=0.94,
    learning_rate=linear_schedule(2.5e-4, 2.5e-6),
    clip_range=linear_schedule(0.15, 0.025),
    batch_size=256,
    n_epochs=4,
    n_steps=128,
    verbose=1)

callback = AutoSave(check_freq=256, num_envs=num_envs,
                    save_path="./models/", filename_prefix="ppo_")

agent.learn(total_timesteps=100000, callback=callback)
agent.save("ppo_doapp_final")
```

### Parallel Training

```bash
diambra run -s=8 -r /path/to/roms python train.py
```

`make_sb3_env()` automatically detects `DIAMBRA_ENVS` and creates a `SubprocVecEnv` with one environment per engine instance.

### Save / Load / Evaluate

```python
# Save
agent.save("ppo_doapp")

# Load
agent = PPO.load("ppo_doapp", env=env)

# Evaluate
from stable_baselines3.common.evaluation import evaluate_policy
mean_reward, std_reward = evaluate_policy(agent, agent.get_env(), n_eval_episodes=10)
```

### YAML Configuration

```yaml
settings:
  game_id: "doapp"
  step_ratio: 6
  frame_shape: [128, 128, 1]
  action_space: "multi_discrete"
  characters: ["Kasumi"]
  difficulty: 3

wrappers_settings:
  normalize_reward: true
  no_attack_buttons_combinations: true
  stack_frames: 4
  dilation: 1
  add_last_action: true
  stack_actions: 12
  scale: true
  exclude_image_scaling: true
  role_relative: true
  flatten: true
  filter_keys: ["action", "own_health", "opp_health", "own_side", "opp_side", "stage", "timer"]

ppo:
  gamma: 0.94
  learning_rate: [2.5e-4, 2.5e-6]
  clip_range: [0.15, 0.025]
  batch_size: 256
  n_epochs: 4
  n_steps: 128

autosave_freq: 256
time_steps: 100000
```

---

## 10. Two-Player / Self-Play

### Basic 2P Environment

```python
from diambra.arena import EnvironmentSettingsMultiAgent, SpaceTypes
import diambra.arena

settings = EnvironmentSettingsMultiAgent()
settings.action_space = (SpaceTypes.DISCRETE, SpaceTypes.DISCRETE)
settings.characters = ("Ryu", "Ken")

env = diambra.arena.make("sfiii3n", settings, render_mode="human")
obs, info = env.reset(seed=42)

while True:
    actions = env.action_space.sample()
    # actions = {"agent_0": action_0, "agent_1": action_1}

    obs, reward, terminated, truncated, info = env.step(actions)
    # reward: {"agent_0": +R, "agent_1": -R}

    if terminated or truncated:
        break

env.close()
```

### Self-Play with Trained Model

```python
from stable_baselines3 import PPO

model = PPO.load("checkpoint")

# Both agents use the same model
# Swap P2 observation keys to P1 format for model compatibility
obs_p1 = extract_agent_obs(obs, "P1")
obs_p2 = extract_agent_obs(obs, "P2", remap_to="P1")

action_p1, _ = model.predict(obs_p1, deterministic=False)
action_p2, _ = model.predict(obs_p2, deterministic=False)

actions = {"agent_0": action_p1, "agent_1": action_p2}
```

**Self-play training loop (for Rawl TaaS):**
1. Both agents share the same policy network initially
2. Every 100K steps, save current policy as a historical opponent
3. 70% matches against self, 30% against random historical policies
4. Track Elo across checkpoints

---

## 11. Supported Games

| Game | ID | Discrete | MultiDiscrete | Characters | Health Range |
|------|----|----------|---------------|------------|-------------|
| Dead Or Alive ++ | `doapp` | 16 | 72 | 11 | 0–208 |
| SF III 3rd Strike | `sfiii3n` | 18 | 90 | 20 | 0–176 |
| Tekken Tag Tournament | `tektagt` | 21 | 117 | 39 | 0–227 |
| Ultimate MK 3 | `umk3` | 15 | 63 | 26 | 0–166 |
| Samurai Showdown 5 Sp | `samsh5sp` | 19 | 99 | 28 | 0–125 |
| KOF 98 UMH | `kof98umh` | 17 | 81 | 45 | 0–119 |
| Marvel vs Capcom | `mvsc` | 27 | 171 | 22 | varies |
| X-Men vs SF | `xmvsf` | 26 | 162 | 19 | varies |
| Soul Calibur | `soulclbr` | 21 | 117 | 18 | 0–240 |

All games share 9 movement actions. Attack counts vary: 7 (UMK3) to 19 (MvC).

---

## 12. gRPC Interface

The `DiambraEngine` class (`diambra/arena/engine/interface.py`) wraps gRPC:

```python
class DiambraEngine:
    def __init__(self, env_address, grpc_timeout=60):
        # Establishes gRPC channel to engine

    def env_init(self, env_settings_pb):
        # Sends EnvironmentSettings protobuf, returns game metadata

    def reset(self, episode_settings_pb):
        # Resets game state, returns initial observation

    def step(self, actions):
        # Sends Actions protobuf (each with .move and .attack fields)
        # Returns observation + reward + done

    def close(self):
        # Sends Empty protobuf, closes channel
```

Address resolution: reads `DIAMBRA_ENVS` env var → splits by space → assigns by rank index.

---

## 13. Key Source Files

| File | Purpose |
|------|---------|
| `diambra/arena/__init__.py` | Package exports: `make()`, settings classes |
| `diambra/arena/make_env.py` | `make()` factory: selects 1P/2P, applies wrappers |
| `diambra/arena/arena_gym.py` | `DiambraGym1P` and `DiambraGym2P` Gymnasium envs |
| `diambra/arena/env_settings.py` | `EnvironmentSettings`, `WrappersSettings`, etc. |
| `diambra/arena/engine/interface.py` | `DiambraEngine` gRPC client |
| `diambra/arena/stable_baselines3/make_sb3_env.py` | `make_sb3_env()` vectorized env factory |
| `diambra/arena/wrappers/` | All observation/action/reward wrappers |
| `diambra/agents/stable_baselines3/training.py` | Full SB3 training pipeline example |
| `diambra/agents/stable_baselines3/cfg_files/` | YAML configs for training |

---

## 14. Relevance to Rawl

| DIAMBRA Component | Rawl Usage |
|-------------------|-----------|
| Docker Engine + gRPC | Match Runner spins up containers per match; TaaS spins up per training job |
| `diambra-arena` Python API | Both Match Runner and training workers use `env.step()` / `env.reset()` |
| 2-Player mode | Used for both self-play training and live matches |
| `make_sb3_env()` + SubprocVecEnv | TaaS training workers use this for parallel training |
| WrappersSettings | Standardized wrapper config for all platform-trained fighters |
| Frame output (`rgb_array`) | Match Runner captures RGB frames for MJPEG streaming |
| RAM observations (`info` dict) | Game Adapters extract match state for data channel + result determination |
| Model save/load (SB3 `.zip`) | Agent Registry stores and serves model checkpoints |
| `DIAMBRA_ENVS` env var | Platform manages Docker containers and populates endpoints dynamically |

---

*Last updated: February 14, 2026*
