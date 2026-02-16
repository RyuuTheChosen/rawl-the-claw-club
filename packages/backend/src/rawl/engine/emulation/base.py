from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


class EmulationEngine(ABC):
    """Abstract base for game emulation engines.

    Provides a uniform start/step/stop interface so match_runner is
    engine-agnostic.  Concrete implementations translate engine-specific
    formats into the canonical nested dict format expected by game adapters.
    """

    @abstractmethod
    def start(self) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Boot the emulator, load the ROM, and return (obs, info).

        obs:  {"P1": np.ndarray(H,W,3), "P2": np.ndarray(H,W,3)}
        info: nested dict matching adapter format
              {"P1": {"health": ..., ...}, "P2": {...}, "timer": ..., ...}
        """
        ...

    @abstractmethod
    def step(
        self, action: dict[str, np.ndarray]
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Advance one frame.

        Args:
            action: {"P1": action_array, "P2": action_array}

        Returns:
            (obs, reward, terminated, truncated, info) — same formats as start().
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Release all emulator resources."""
        ...
