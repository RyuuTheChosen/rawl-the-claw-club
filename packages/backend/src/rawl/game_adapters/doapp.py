from __future__ import annotations

from rawl.game_adapters.base import GameAdapter, MatchState


class DOAPPAdapter(GameAdapter):
    """Dead or Alive++ adapter — stub."""

    game_id = "doapp"
    adapter_version = "0.0.1"
    required_fields = ["health", "round", "timer", "stage_side"]

    def extract_state(self, info: dict) -> MatchState:
        raise NotImplementedError("DOAPP adapter is not yet implemented")

    def is_round_over(self, info: dict, *, state: MatchState | None = None) -> str | bool:
        raise NotImplementedError("DOAPP adapter is not yet implemented")

    def is_match_over(
        self,
        info: dict,
        round_history: list[dict],
        *,
        state: MatchState | None = None,
        match_format: int = 3,
    ) -> str | bool:
        raise NotImplementedError("DOAPP adapter is not yet implemented")
