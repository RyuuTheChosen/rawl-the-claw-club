# RL Pipeline Development Log

Date: 2026-02-17

## What Was Done

End-to-end setup of the reinforcement learning training and inference pipeline for SF2 Champion Edition (Genesis) on stable-retro.

### 1. Inference Pipeline Update

Updated the backend match engine from the old 128x128x1 format to the DeepMind standard used by all successful SF2 RL projects.

**`packages/backend/src/rawl/engine/frame_processor.py`**
- Changed `preprocess_for_inference()` from 128x128x1 to 84x84x1 grayscale (WarpFrame standard)

**`packages/backend/src/rawl/engine/match_runner.py`**
- Added 4-frame stacking via `collections.deque` buffers (one per player)
- Added `FRAME_STACK_N = 4` constant — must match training `VecFrameStack(n_stack=4)`
- Each frame: preprocess to 84x84x1 → append to deque → concatenate to (84,84,4)

**`packages/backend/src/rawl/training/validation.py`**
- Updated random obs shape from `(128, 128, 1)` to `(84, 84, 4)` in all validation steps

**`packages/backend/src/rawl/training/pipeline.py`**
- Changed policy from `MlpPolicy` to `CnnPolicy` (image-based obs require CNN)

### 2. Training Script

Created `scripts/train_sf2_baseline.py` — a complete PPO training script with research-backed configuration.

**Key components:**
- `SF2RewardWrapper` — Asymmetric health-delta reward (3x coefficient for damage dealt vs taken), exponential round-win/loss bonuses scaled by remaining HP, global 0.001 scaling
- `StochasticFrameSkip` — Skip 4 frames with 25% sticky-action probability
- `linear_schedule()` — Learning rate 2.5e-4 → 0, clip range 0.15 → 0.025
- Uses `WarpFrame` (84x84 grayscale) + `VecFrameStack(n_stack=4)` + `VecTransposeImage`
- No `ClipRewardEnv` (destroys round-win bonus signal)
- `SubprocVecEnv` for parallel envs, `CheckpointCallback` at 500K intervals

**Hyperparameters:** gamma=0.94, n_steps=512, batch_size=512, n_epochs=4, ent_coef=0.01

**Usage:**
```bash
SDL_VIDEODRIVER=dummy python3 scripts/train_sf2_baseline.py \
    --timesteps 5000000 --n-envs 8 --output models/sf2_baseline
```

### 3. RL Research & Training Guide

Created `docs/rl-training-guide.md` covering:
- Algorithm choice (PPO, why not DQN/SAC)
- Reward shaping with the asymmetric coefficient explanation
- Battle-tested hyperparameters with rationale for each value
- Observation space and action space decisions
- 4-phase training pipeline: CPU Baseline → Opponent Rotation → Self-Play → Multi-Style
- Training duration expectations (500K through 10M+ steps)
- References to linyiLYi, thuongmhh, HadouQen, FightLadder

### 4. ROCm GPU Setup (AMD 9070 XT)

Configured AMD ROCm 7.2 in WSL2 for GPU-accelerated training:
- Installed ROCm 7.2 via `amdgpu-install --usecase=wsl,rocm --no-dkms`
- Installed PyTorch ROCm wheels (torch 2.9.1+rocm7.2.0)
- Removed bundled HSA runtime from torch lib dir (conflicts with system HSA)
- Verified: `rocminfo` shows gfx1201, `torch.cuda.is_available()` returns True

**Finding:** GPU doesn't significantly speed up SF2 training (~490 fps vs ~500 fps CPU). The bottleneck is environment stepping in stable-retro (CPU-bound), not the CNN forward/backward pass. GPU matters more for larger networks or when running many envs.

### 5. Match Viewer Multi-Model Support

Updated `scripts/watch_match.py` to load and auto-detect three model formats:

| Type | Obs Shape | Action Space | Notes |
|------|-----------|-------------|-------|
| Rawl | (84,84,4) | MultiBinary | Our standard format |
| thuongmhh | (84,84,4) | Discrete(15) | Needs discrete→multibinary LUT |
| linyiLYi | (3,100,128) | MultiBinary(12) | Custom RGB stacking |

**Added:**
- `detect_model_type()` — auto-detection from obs shape + action space
- `FrameStacker84` — 84x84 grayscale, 4-frame stack
- `FrameStackerLinyiLYi` — 100x128 RGB, 9-frame buffer with channel picking
- `SF2_DISCRETE_COMBOS` — lookup table mapping Discrete(15) → MultiBinary(12) button masks
- `FRAME_SKIP = 4` — frame skip in viewer to match training conditions

### 6. Pre-trained Model Evaluation

Downloaded and tested two open-source models head-to-head:
- **thuongmhh** (`models/pretrained/thuongmhh_discrete15.zip`) — 20MB, Discrete(15)
- **linyiLYi** (`models/pretrained/linyiLYi_2500k.zip`) — 42MB, MultiBinary(12), 2.5M steps

**Result:** linyiLYi dominates from either side. thuongmhh's policy is fundamentally defensive (87% retreating) due to symmetric reward. linyiLYi's asymmetric 3x reward coefficient produces aggressive, engaging play.

This confirmed the asymmetric reward approach adopted in our training script.

### 7. Initial Training Run

Ran a 2M-step training on CPU (before tuning):
- ~63 minutes, ~500 fps, 10 checkpoints saved
- Output: `models/sf2_baseline.zip`
- Result: Random-looking play — expected with symmetric rewards and insufficient steps

## WSL2 Dependencies Installed

```bash
# Core
pip3 install stable-baselines3 opencv-python-headless tensorboard tqdm rich

# For pre-trained model loading
pip3 install gym "shimmy>=2.0" numpy>=2.0

# ROCm (optional, for GPU)
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/rocm7.2
```

## Files Changed/Created

| File | Action | Description |
|------|--------|-------------|
| `scripts/train_sf2_baseline.py` | Created | PPO training script with tuned hyperparameters |
| `scripts/watch_match.py` | Modified | Multi-model support, auto-detection, frame skip |
| `docs/rl-training-guide.md` | Created | RL research findings and 4-phase training pipeline |
| `packages/backend/src/rawl/engine/frame_processor.py` | Modified | 128x128 → 84x84 obs preprocessing |
| `packages/backend/src/rawl/engine/match_runner.py` | Modified | Added 4-frame stacking buffers |
| `packages/backend/src/rawl/training/validation.py` | Modified | Updated obs shape to (84,84,4) |
| `packages/backend/src/rawl/training/pipeline.py` | Modified | MlpPolicy → CnnPolicy |

## Next Steps

1. Run tuned 5M-step training with asymmetric reward (`scripts/train_sf2_baseline.py`)
2. Evaluate output as the "house bot" / Phase 1 agent
3. Proceed through Phase 2 (opponent rotation) and Phase 3 (self-play) per the training guide
4. Integrate trained model into the match engine as the default opponent
