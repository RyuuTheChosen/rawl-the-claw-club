#!/usr/bin/env python3
"""Train a PPO agent for SF2 Champion Edition (Genesis).

Tuned based on findings from linyiLYi/street-fighter-ai, HadouQen,
and FightLadder (ICML 2024). See docs/rl-training-guide.md.

Requirements (install in WSL2):
    pip3 install stable-baselines3 opencv-python-headless tensorboard tqdm rich

Run:
    SDL_VIDEODRIVER=dummy python3 scripts/train_sf2_baseline.py

Options:
    --timesteps 5000000     Total training steps (default: 5M)
    --n-envs 8              Parallel environments (default: 8)
    --output models/sf2     Output path without .zip (default: models/sf2_baseline)
    --resume models/sf2.zip Resume training from checkpoint

Monitor:
    tensorboard --logdir models/sf2_logs/
"""

import argparse
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import gymnasium as gym
import numpy as np
from gymnasium.wrappers import TimeLimit
from stable_baselines3 import PPO
from stable_baselines3.common.atari_wrappers import WarpFrame
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import (
    DummyVecEnv,
    SubprocVecEnv,
    VecFrameStack,
    VecMonitor,
    VecTransposeImage,
)

import stable_retro as retro

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"
MAX_HEALTH = 176

# Asymmetric reward coefficient — damage dealt weighted higher than damage
# taken to prevent the agent from learning to run away (the "cowardice problem").
# Value of 3.0 from linyiLYi/street-fighter-ai (beat M. Bison).
REWARD_COEFF = 3.0

# Global scaling factor for numerical stability (prevents reward magnitude issues).
REWARD_SCALE = 0.001


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------


class StochasticFrameSkip(gym.Wrapper):
    """Skip n frames with sticky-action probability (from stable_retro examples)."""

    def __init__(self, env, n=4, stickprob=0.25):
        super().__init__(env)
        self.n = n
        self.stickprob = stickprob
        self.curac = None
        self.rng = np.random.RandomState()

    def reset(self, **kwargs):
        self.curac = None
        return self.env.reset(**kwargs)

    def step(self, ac):
        terminated = False
        truncated = False
        totrew = 0
        for i in range(self.n):
            if self.curac is None:
                self.curac = ac
            elif i == 0:
                if self.rng.rand() > self.stickprob:
                    self.curac = ac
            elif i == 1:
                self.curac = ac
            ob, rew, terminated, truncated, info = self.env.step(self.curac)
            totrew += rew
            if terminated or truncated:
                break
        return ob, totrew, terminated, truncated, info


class SF2RewardWrapper(gym.Wrapper):
    """Asymmetric health-delta reward for fighting games.

    Per-step:
        reward = REWARD_COEFF * dmg_dealt - dmg_taken

    Round win:
        reward += pow(MAX_HEALTH, (player_hp + 1) / (MAX_HEALTH + 1)) * REWARD_COEFF

    Round loss:
        reward -= pow(MAX_HEALTH, (enemy_hp + 1) / (MAX_HEALTH + 1))

    All rewards scaled by REWARD_SCALE for numerical stability.

    Based on linyiLYi/street-fighter-ai reward function.
    """

    def __init__(self, env):
        super().__init__(env)
        self._prev_hp = MAX_HEALTH
        self._prev_enemy_hp = MAX_HEALTH
        self._prev_wins = 0
        self._prev_enemy_wins = 0

    def step(self, action):
        obs, _reward, terminated, truncated, info = self.env.step(action)

        hp = max(0, info.get("health", 0))
        enemy_hp = max(0, info.get("enemy_health", 0))
        wins = info.get("matches_won", 0)
        enemy_wins = info.get("enemy_matches_won", 0)

        # Asymmetric health-delta: attack rewarded 3x more than defense
        dmg_dealt = max(0, self._prev_enemy_hp - enemy_hp)
        dmg_taken = max(0, self._prev_hp - hp)
        reward = REWARD_COEFF * dmg_dealt - dmg_taken

        # Exponential round bonuses scaled by remaining HP
        if wins > self._prev_wins:
            reward += pow(MAX_HEALTH, (hp + 1) / (MAX_HEALTH + 1)) * REWARD_COEFF
        if enemy_wins > self._prev_enemy_wins:
            reward -= pow(MAX_HEALTH, (enemy_hp + 1) / (MAX_HEALTH + 1))

        # Scale everything for numerical stability
        reward *= REWARD_SCALE

        self._prev_hp = hp
        self._prev_enemy_hp = enemy_hp
        self._prev_wins = wins
        self._prev_enemy_wins = enemy_wins

        return obs, reward, terminated, truncated, info

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._prev_hp = MAX_HEALTH
        self._prev_enemy_hp = MAX_HEALTH
        self._prev_wins = 0
        self._prev_enemy_wins = 0
        return obs, info


# ---------------------------------------------------------------------------
# Linear schedule helpers
# ---------------------------------------------------------------------------


def linear_schedule(initial: float, final: float = 0.0):
    """Return a function that linearly interpolates from initial to final."""

    def _schedule(progress_remaining: float) -> float:
        return final + progress_remaining * (initial - final)

    return _schedule


# ---------------------------------------------------------------------------
# Environment factory
# ---------------------------------------------------------------------------


def make_env(state=None, max_episode_steps=4500):
    def _init():
        env = retro.make(
            GAME,
            state=state or retro.State.DEFAULT,
            players=1,
            use_restricted_actions=retro.Actions.FILTERED,
            render_mode="rgb_array",
        )
        env = SF2RewardWrapper(env)
        env = StochasticFrameSkip(env, n=4, stickprob=0.25)
        if max_episode_steps is not None:
            env = TimeLimit(env, max_episode_steps=max_episode_steps)
        env = WarpFrame(env)  # 84x84 grayscale
        # No ClipRewardEnv — preserves round-win bonus signal
        return env

    return _init


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Train SF2 PPO agent")
    parser.add_argument("--timesteps", type=int, default=5_000_000)
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument("--output", type=str, default="models/sf2_baseline")
    parser.add_argument("--checkpoint-freq", type=int, default=500_000)
    parser.add_argument("--state", type=str, default=None)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output) or "models"
    os.makedirs(output_dir, exist_ok=True)
    log_dir = os.path.join(output_dir, "sf2_logs")

    # Build vectorized environment
    env_fns = [make_env(state=args.state) for _ in range(args.n_envs)]
    if args.n_envs > 1:
        venv = SubprocVecEnv(env_fns)
    else:
        venv = DummyVecEnv(env_fns)
    venv = VecMonitor(venv)
    venv = VecFrameStack(venv, n_stack=4)
    venv = VecTransposeImage(venv)

    # Create or resume model
    if args.resume:
        print(f"Resuming from {args.resume}")
        model = PPO.load(args.resume, env=venv)
    else:
        model = PPO(
            policy="CnnPolicy",
            env=venv,
            learning_rate=linear_schedule(2.5e-4),
            n_steps=512,
            batch_size=512,
            n_epochs=4,
            gamma=0.94,
            gae_lambda=0.95,
            clip_range=linear_schedule(0.15, 0.025),
            ent_coef=0.01,
            verbose=1,
            tensorboard_log=log_dir,
        )

    checkpoint_cb = CheckpointCallback(
        save_freq=max(args.checkpoint_freq // args.n_envs, 1),
        save_path=output_dir,
        name_prefix="sf2_checkpoint",
    )

    print(f"Training {GAME} for {args.timesteps:,} timesteps ({args.n_envs} envs)")
    print(f"Hyperparams: gamma=0.94, n_steps=512, batch=512, clip=0.15->0.025")
    print(f"Reward: asymmetric (coeff={REWARD_COEFF}, scale={REWARD_SCALE})")
    print(f"Checkpoints -> {output_dir}/")
    print(f"Tensorboard -> tensorboard --logdir {log_dir}")

    model.learn(
        total_timesteps=args.timesteps,
        callback=checkpoint_cb,
        log_interval=1,
        progress_bar=True,
    )

    model.save(args.output)
    print(f"\nSaved to {args.output}.zip")
    venv.close()


if __name__ == "__main__":
    main()
