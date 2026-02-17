# Reinforcement Learning Training Guide — SF2 Champion Edition

## Algorithm

PPO is the proven choice. Every successful SF2 RL project uses it (linyiLYi, HadouQen, thuongmhh). DQN works but is less sample-efficient on visual inputs. SAC is designed for continuous control and doesn't fit discrete fighting game actions.

## Reward Shaping

Symmetric health-delta rewards cause agents to learn defensive/evasive behavior. The fix is an asymmetric coefficient.

**Proven reward function (linyiLYi — beat M. Bison):**

```
Per-step:  reward = 3.0 * (prev_enemy_hp - curr_enemy_hp) - (prev_hp - curr_hp)
Round win: reward = +pow(176, (player_hp + 1) / 177) * 3.0
Round loss: reward = -pow(176, (enemy_hp + 1) / 177)
Final:     reward *= 0.001  (scaling for numerical stability)
```

Key insights:
- 3x asymmetric coefficient prevents cowardice — agent learns to engage
- Exponential round bonuses reward winning with more HP remaining
- Score-based, position-based, and combo-detection rewards add noise without improving win rate
- `ClipRewardEnv` destroys the round-win bonus signal — avoid it

## Hyperparameters

**Battle-tested PPO config for SF2:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| gamma | 0.94 | Rounds are short (~20-30s). Low gamma focuses on immediate exchanges |
| n_steps | 512 | Captures significant chunk of a round per rollout |
| batch_size | 512 | Better gradient estimates |
| n_epochs | 4 | Standard |
| learning_rate | 2.5e-4 → 0 (linear decay) | Standard with linear schedule |
| clip_range | 0.15 → 0.025 (linear decay) | Wide exploration early, stable late |
| ent_coef | 0.01 | Prevents premature convergence to repetitive strategies |
| gae_lambda | 0.95 | Standard |
| n_envs | 8-16 | More sample diversity, better parallelism |

Sources: linyiLYi/street-fighter-ai, RL Baselines3 Zoo Atari config, HadouQen paper.

## Observation Space

84x84 grayscale + 4-frame stack (DeepMind standard). This is what `WarpFrame` + `VecFrameStack(n_stack=4)` provides. Matches our inference pipeline (`preprocess_for_inference()` in `frame_processor.py`).

Alternatives tested elsewhere:
- 100x128 RGB subsampled — retains color but non-standard shape
- RAM features (30-element vector) — fast to train but brittle and game-specific

Stick with 84x84 grayscale for Rawl's standardized model format.

## Action Space

`retro.Actions.FILTERED` gives `MultiBinary(12)` per player (Genesis: B, A, MODE, START, UP, DOWN, LEFT, RIGHT, C, Y, X, Z). PPO handles MultiBinary natively.

If convergence is slow, a `Discretizer` wrapper mapping to ~20 meaningful actions (directions + individual attacks + common 2-button combos) can help. The thuongmhh project used Discrete(14) and achieved 100% win rate.

Do NOT hardcode special move sequences as single actions — let the agent learn frame-by-frame inputs through frame skipping.

## Training Duration

| Timesteps | Behavior |
|-----------|----------|
| 500K | Starts blocking some attacks |
| 1-2M | Basic attack patterns emerge |
| 2-3M | Reliably wins rounds |
| 5-7M | Strong agent, may start overfitting to CPU patterns |
| 10M+ | Diminishing returns vs CPU — transition to self-play |

Frame skip factor: with `StochasticFrameSkip(n=4)`, 5M timesteps = 20M game frames.

The linyiLYi project beat the final boss at 2.5M timesteps but used frame skip of 6 (= 15M game frames). Accounting for frame skip, our 5M steps at skip=4 covers 20M frames — comparable.

## Training Pipeline

The full pipeline has 4 phases. Each phase builds on the previous one's checkpoint.

### Phase 1 — CPU Baseline (5M steps, ~2.5 hours on 8 envs)

**Goal:** Learn fundamentals — blocking, basic attacks, spacing, round structure.

**Setup:**
- Train against the built-in CPU on default state (Ryu vs Guile, Level 1)
- Single matchup, single difficulty
- Standard reward function (asymmetric 3x coefficient)

**Script:**
```bash
SDL_VIDEODRIVER=dummy python3 scripts/train_sf2_baseline.py \
    --timesteps 5000000 --n-envs 8 --output models/sf2_phase1
```

**What to expect:**
- 500K steps — starts blocking some attacks
- 1-2M steps — basic attack patterns emerge (jabs, sweeps)
- 2-3M steps — reliably wins rounds against Level 1 CPU
- 5M steps — strong against Level 1, but overfitted to Guile's patterns

**Done when:** Agent reliably wins 80%+ of rounds in the viewer. Output is the "house bot" / default opponent for the platform.

### Phase 2 — Opponent Rotation (5M more steps, resume from Phase 1)

**Goal:** Generalize beyond one matchup. Prevent single-opponent overfitting.

**Setup:**
- Resume from Phase 1 checkpoint
- Randomly rotate through multiple CPU opponents and difficulty levels per episode
- Use save states: Level 1 through Level 8, different character matchups
- Same reward function and hyperparameters

**Script:**
```bash
SDL_VIDEODRIVER=dummy python3 scripts/train_sf2_baseline.py \
    --timesteps 5000000 --n-envs 8 --output models/sf2_phase2 \
    --resume models/sf2_phase1.zip
```

**What to expect:**
- Initial performance drop as agent encounters unfamiliar opponents
- 1-2M steps — adapts to multiple matchups
- 3-5M steps — generalized fighting style, no longer exploits one opponent's patterns
- Agent may still lose to higher-difficulty CPU (Level 10-12)

**Done when:** Agent wins 60%+ across multiple opponents/levels. This is the minimum viable agent for competitive play.

### Phase 3 — Self-Play (5-10M+ steps, resume from Phase 2)

**Goal:** Build a competitive agent that can't be exploited by other trained agents.

**Setup:**
- Resume from Phase 2 checkpoint
- Stop training against CPU entirely
- Train against a pool of its own past checkpoints
- Pool composition: 70% recent checkpoints, 30% historical (prevents cyclic forgetting)
- Our `SelfPlayCallback` (`packages/backend/src/rawl/training/self_play.py`) implements this

**Script:**
```bash
SDL_VIDEODRIVER=dummy python3 scripts/train_sf2_selfplay.py \
    --timesteps 10000000 --n-envs 8 --output models/sf2_phase3 \
    --resume models/sf2_phase2.zip --pool-size 20 --save-freq 100000
```

**What to expect:**
- Elo climbs steadily as agent improves against increasingly strong opponents
- Develops counter-strategies, mixups, and defensive play
- Simple self-play (always vs latest checkpoint) causes cyclic non-convergence — the historical pool prevents this
- FightLadder (ICML 2024) showed population-based self-play significantly outperforms independent PPO

**Risk:** Without the historical pool, agent A beats B, B' beats A, A' beats B' — infinite loop with no net progress.

**Done when:** Elo plateaus over 500K steps. This is the competitive agent for wagered matches.

### Phase 4 — Multi-Style Training (optional, for top-tier agents)

**Goal:** Create an agent that can handle any playstyle.

**Setup:**
- Train 3 agent variants from the Phase 2 checkpoint, each with different reward weightings:
  - **Aggressive** — `REWARD_COEFF = 5.0` (heavily rewards attacking)
  - **Defensive** — `REWARD_COEFF = 1.0` (balanced damage dealt/taken)
  - **Balanced** — `REWARD_COEFF = 3.0` (standard)
- Train each for 3-5M steps via self-play
- Train a final agent against a pool containing all 3 styles

**What to expect:**
- Final agent develops adaptive play — aggressive against defensive opponents, patient against aggressive ones
- Used in the Blade & Soul paper to achieve 62% win rate vs professional human players

**Done when:** Agent beats all 3 specialist styles >50% of the time.

### Pipeline Summary

| Phase | Steps | Input | Output | Time (8 envs) |
|-------|-------|-------|--------|----------------|
| 1. CPU Baseline | 5M | scratch | `sf2_phase1.zip` | ~2.5h |
| 2. Opponent Rotation | 5M | phase1 | `sf2_phase2.zip` | ~2.5h |
| 3. Self-Play | 10M | phase2 | `sf2_phase3.zip` | ~5h |
| 4. Multi-Style | 15M+ | phase2 | `sf2_final.zip` | ~8h |

Total for a competitive agent (Phases 1-3): ~20M steps, ~10 hours.

### Rawl Platform Integration

- **Phase 1 output** → ships as the "house bot" / default opponent for new users
- **Phase 2 output** → baseline agent that isn't exploitable by one trick
- **Phase 3 output** → competitive agent for wagered matches, uploaded to S3 as a fighter's `model_s3_key`
- Users train their own agents off-platform via `rawl-trainer`, submit models through the gateway API, and the match engine runs them head-to-head using the inference pipeline (`frame_processor.py` + `match_runner.py`)

## Curriculum Strategies

Additional curriculum techniques that can be mixed into any phase:

1. **Opponent difficulty progression** — start on Level 1, advance to Level 12
2. **Single-round then multi-round** — easier value estimation for single rounds
3. **State randomization** — rotate save states to prevent overfitting
4. **Multi-opponent** — train against multiple characters, not just one matchup

## Notable References

### GitHub Projects
- [linyiLYi/street-fighter-ai](https://github.com/linyiLYi/street-fighter-ai) — Gold standard. PPO+SB3, beats final boss. ~4.8k stars
- [thuongmhh/Street-Fighter-AI](https://github.com/thuongmhh/Street-Fighter-AI) — PPO+SB3, Discrete(14), 100% win rate
- [corbosiny/AIVO](https://github.com/corbosiny/AIVO-StreetFigherReinforcementLearning) — DQN, RAM features, tournament self-play
- [Tqualizer/Retro-SF-RL](https://github.com/Tqualizer/Retro-Street-Fighter-reinforcement-learning) — PPO2 vs brute-force comparison

### Papers
- HadouQen (2025) — PPO, 16 envs, 100M steps, 96.7% win rate vs M. Bison
- FightLadder (ICML 2024) — Multi-algorithm benchmark for fighting games
- Blade & Soul (2019) — Self-play curriculum, 62% vs human pros

### Tooling
- [RL Baselines3 Zoo](https://github.com/DLR-RM/rl-baselines3-zoo) — Official SB3 hyperparameter configs
- [SB3 RL Tips and Tricks](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html) — Reward normalization, frame stacking
