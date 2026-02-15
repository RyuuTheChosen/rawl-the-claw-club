from __future__ import annotations

from rawl.game_adapters.base import GameAdapter, MatchState


class SFIII3NAdapter(GameAdapter):
    """Street Fighter III: 3rd Strike adapter."""

    game_id = "sfiii3n"
    adapter_version = "1.0.0"
    required_fields = ["health", "round", "timer", "stage_side"]

    MAX_HEALTH = 176

    def extract_state(self, info: dict) -> MatchState:
        return MatchState(
            p1_health=max(0.0, info["P1"].get("health", 0) / self.MAX_HEALTH),
            p2_health=max(0.0, info["P2"].get("health", 0) / self.MAX_HEALTH),
            round_number=info.get("round", 0),
            timer=info.get("timer", 0),
            stage_side=info["P1"].get("stage_side", 0),
            combo_count=info["P1"].get("combo_count", 0),
        )

    def is_round_over(
        self, info: dict, *, state: MatchState | None = None
    ) -> str | bool:
        p1_health = info["P1"].get("health", 0)
        p2_health = info["P2"].get("health", 0)
        timer = info.get("timer", 99)

        # KO checks
        if p1_health <= 0 and p2_health <= 0:
            return "DRAW"
        if p1_health <= 0:
            return "P2"
        if p2_health <= 0:
            return "P1"

        # Timeout
        if timer <= 0:
            if p1_health > p2_health:
                return "P1"
            elif p2_health > p1_health:
                return "P2"
            else:
                return "DRAW"

        return False

    def is_match_over(
        self,
        info: dict,
        round_history: list[dict],
        *,
        state: MatchState | None = None,
        match_format: int = 3,
    ) -> str | bool:
        wins_needed = (match_format // 2) + 1
        p1_wins = sum(1 for r in round_history if r.get("winner") == "P1")
        p2_wins = sum(1 for r in round_history if r.get("winner") == "P2")

        if p1_wins >= wins_needed:
            return "P1"
        if p2_wins >= wins_needed:
            return "P2"
        return False
