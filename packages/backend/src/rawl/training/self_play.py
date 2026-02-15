"""Self-play training callback for SB3 PPO.

Maintains a checkpoint pool and samples opponents:
  70% from recent self-play checkpoints
  30% from historical checkpoint versions
"""
from __future__ import annotations

import logging
import random
import tempfile
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

logger = logging.getLogger(__name__)


class SelfPlayCallback(BaseCallback):
    """SB3 callback for self-play training.

    Every `checkpoint_interval` steps:
      1. Save current model as a checkpoint
      2. Add to the opponent pool
      3. Sample next opponent: 70% recent, 30% historical
    """

    def __init__(
        self,
        checkpoint_interval: int = 50_000,
        max_pool_size: int = 20,
        recent_ratio: float = 0.7,
        checkpoint_dir: str | None = None,
    ):
        super().__init__()
        self.checkpoint_interval = checkpoint_interval
        self.max_pool_size = max_pool_size
        self.recent_ratio = recent_ratio
        self._checkpoint_dir = Path(checkpoint_dir or tempfile.mkdtemp(prefix="rawl_selfplay_"))
        self._pool: list[Path] = []
        self._last_checkpoint = 0
        self._current_opponent: PPO | None = None

    def _on_step(self) -> bool:
        current = self.num_timesteps
        if current - self._last_checkpoint >= self.checkpoint_interval:
            self._save_checkpoint(current)
            self._last_checkpoint = current
        return True

    def _save_checkpoint(self, timestep: int) -> None:
        """Save current model as checkpoint and add to pool."""
        path = self._checkpoint_dir / f"checkpoint_{timestep}.zip"
        self.model.save(str(path))
        self._pool.append(path)

        # Trim pool if over max size (keep most recent + spread of historical)
        if len(self._pool) > self.max_pool_size:
            # Keep first, last N-1, and remove middle entries
            keep = [self._pool[0]] + self._pool[-(self.max_pool_size - 1):]
            removed = [p for p in self._pool if p not in keep]
            for p in removed:
                p.unlink(missing_ok=True)
            self._pool = keep

        logger.info(
            "Self-play checkpoint saved",
            extra={"timestep": timestep, "pool_size": len(self._pool)},
        )

    def sample_opponent(self) -> PPO | None:
        """Sample an opponent from the checkpoint pool.

        70% chance: recent checkpoint (last 30% of pool)
        30% chance: historical checkpoint (first 70% of pool)
        """
        if not self._pool:
            return None

        pool_size = len(self._pool)
        recent_cutoff = max(1, int(pool_size * 0.7))

        if random.random() < self.recent_ratio and pool_size > recent_cutoff:
            # Sample from recent checkpoints
            path = random.choice(self._pool[recent_cutoff:])
        else:
            # Sample from historical checkpoints
            path = random.choice(self._pool[:recent_cutoff])

        try:
            opponent = PPO.load(str(path))
            logger.info("Sampled opponent", extra={"checkpoint": path.name})
            return opponent
        except Exception:
            logger.exception("Failed to load opponent checkpoint")
            return None

    def cleanup(self) -> None:
        """Remove all checkpoint files."""
        for path in self._pool:
            path.unlink(missing_ok=True)
        self._pool.clear()
