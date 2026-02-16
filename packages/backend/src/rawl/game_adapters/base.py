from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from rawl.game_adapters.errors import AdapterValidationError


@dataclass
class MatchState:
    """State extracted from a single frame for standard 1v1 games."""

    p1_health: float  # Normalized 0.0-1.0
    p2_health: float
    round_number: int
    timer: int
    stage_side: int
    combo_count: int = 0


@dataclass
class TeamMatchState(MatchState):
    """Extended state for team-based games (KOF98, Tekken Tag)."""

    p1_team_health: list[float] = field(default_factory=list)
    p2_team_health: list[float] = field(default_factory=list)
    p1_active_character: int = 0
    p2_active_character: int = 0
    p1_eliminations: int = 0
    p2_eliminations: int = 0


class GameAdapter(ABC):
    """Abstract base class for per-game adapters.

    Each adapter translates emulation engine info dicts into normalized MatchState
    and provides game-specific round/match completion logic.
    """

    game_id: str
    adapter_version: str
    required_fields: list[str]

    def validate_info(self, info: dict) -> None:
        """Validate that all required fields exist in the info dict.

        Called on the first frame of each match BEFORE lock_match.
        Raises AdapterValidationError with a list of missing fields.
        """
        missing: dict[str, list[str]] = {}
        for player in ("P1", "P2"):
            player_info = info.get(player, {})
            player_missing = [f for f in self.required_fields if f not in player_info]
            if player_missing:
                missing[player] = player_missing

        if missing:
            raise AdapterValidationError(self.game_id, missing)

    @abstractmethod
    def extract_state(self, info: dict) -> MatchState | TeamMatchState:
        """Extract normalized game state from emulation engine info dict."""
        ...

    @abstractmethod
    def is_round_over(
        self, info: dict, *, state: MatchState | TeamMatchState | None = None
    ) -> str | bool:
        """Check if the current round is over.

        Returns "P1", "P2", "DRAW", or False.
        If state is provided, uses it to avoid re-extraction.
        """
        ...

    @abstractmethod
    def is_match_over(
        self,
        info: dict,
        round_history: list[dict],
        *,
        state: MatchState | TeamMatchState | None = None,
        match_format: int = 3,
    ) -> str | bool:
        """Check if the match is over.

        Returns "P1", "P2", or False.
        """
        ...
