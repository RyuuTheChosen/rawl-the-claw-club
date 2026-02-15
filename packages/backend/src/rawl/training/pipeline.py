from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def create_ppo_config(
    game_id: str,
    total_timesteps: int = 1_000_000,
) -> dict:
    """Create PPO training configuration for a given game.

    Returns config dict for stable-baselines3 PPO.
    """
    return {
        "policy": "MlpPolicy",
        "learning_rate": 3e-4,
        "n_steps": 2048,
        "batch_size": 64,
        "n_epochs": 10,
        "gamma": 0.99,
        "gae_lambda": 0.95,
        "clip_range": 0.2,
        "ent_coef": 0.01,
        "vf_coef": 0.5,
        "max_grad_norm": 0.5,
        "total_timesteps": total_timesteps,
    }
