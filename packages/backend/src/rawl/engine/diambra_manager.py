from __future__ import annotations

import logging

import diambra.arena

from rawl.config import settings

logger = logging.getLogger(__name__)


class DiambraManager:
    """Manages DIAMBRA environment lifecycle for match execution.

    Handles starting/stopping DIAMBRA environments with proper configuration
    for 2-player matches at 256x256 RGB resolution with MultiDiscrete action space.
    """

    def __init__(self, game_id: str, match_id: str) -> None:
        self.game_id = game_id
        self.match_id = match_id
        self._env = None

    def start(self) -> tuple:
        """Start a DIAMBRA environment and return (obs, info).

        Configuration:
            - Resolution: 256x256 RGB
            - Players: 2 (2P mode)
            - Action space: MultiDiscrete
            - ROM path: from settings
        """
        logger.info(
            "Starting DIAMBRA environment",
            extra={"game_id": self.game_id, "match_id": self.match_id},
        )

        env_settings = self.get_env_settings()
        self._env = diambra.arena.make(self.game_id, env_settings)
        obs, info = self._env.reset()
        return obs, info

    def step(self, action: dict):
        """Step the environment with a combined action dict.

        Args:
            action: {"P1": action_array, "P2": action_array}

        Returns:
            (obs, reward, terminated, truncated, info)
        """
        if not self._env:
            raise RuntimeError("DIAMBRA environment not started")
        return self._env.step(action)

    def stop(self) -> None:
        """Stop and clean up the DIAMBRA environment."""
        if self._env:
            logger.info(
                "Stopping DIAMBRA environment",
                extra={"match_id": self.match_id},
            )
            try:
                self._env.close()
            except Exception:
                logger.exception("Error closing DIAMBRA environment")
            self._env = None

    def get_env_settings(self) -> dict:
        """Build DIAMBRA environment settings."""
        return {
            "game_id": self.game_id,
            "frame_shape": (256, 256, 3),
            "characters": None,  # Random
            "action_space": "multi_discrete",
            "n_players": 2,
            "rom_path": settings.diambra_rom_path,
        }
