from __future__ import annotations

from rawl.game_adapters.base import GameAdapter, TeamMatchState


class TekkenTagAdapter(GameAdapter):
    """Tekken Tag Tournament adapter — 2-character tag team."""

    game_id = "tektagt"
    adapter_version = "1.0.0"
    required_fields = ["health", "tag_health", "active_character", "stage_side"]

    MAX_HEALTH = 170
    DIRECTIONAL_INDICES = {"left": 6, "right": 7}

    def extract_state(self, info: dict) -> TeamMatchState:
        p1_active_health = max(0.0, info["P1"].get("health", 0) / self.MAX_HEALTH)
        p1_tag_health = max(0.0, info["P1"].get("tag_health", 0) / self.MAX_HEALTH)
        p2_active_health = max(0.0, info["P2"].get("health", 0) / self.MAX_HEALTH)
        p2_tag_health = max(0.0, info["P2"].get("tag_health", 0) / self.MAX_HEALTH)

        p1_active = info["P1"].get("active_character", 0)
        p2_active = info["P2"].get("active_character", 0)

        # Build team health arrays — index 0 = point, index 1 = tag partner
        if p1_active == 0:
            p1_team = [p1_active_health, p1_tag_health]
        else:
            p1_team = [p1_tag_health, p1_active_health]

        if p2_active == 0:
            p2_team = [p2_active_health, p2_tag_health]
        else:
            p2_team = [p2_tag_health, p2_active_health]

        return TeamMatchState(
            p1_health=p1_active_health,
            p2_health=p2_active_health,
            round_number=info.get("round", 0),
            timer=info.get("timer", 0),
            stage_side=info["P1"].get("stage_side", 0),
            combo_count=info["P1"].get("combo_count", 0),
            p1_team_health=p1_team,
            p2_team_health=p2_team,
            p1_active_character=p1_active,
            p2_active_character=p2_active,
            p1_eliminations=sum(1 for h in p1_team if h <= 0.0),
            p2_eliminations=sum(1 for h in p2_team if h <= 0.0),
        )

    def is_round_over(
        self, info: dict, *, state: TeamMatchState | None = None
    ) -> str | bool:
        """In Tekken Tag, a round ends when either character on a side is KO'd."""
        if state is None:
            state = self.extract_state(info)

        p1_any_ko = any(h <= 0.0 for h in state.p1_team_health)
        p2_any_ko = any(h <= 0.0 for h in state.p2_team_health)

        if p1_any_ko and p2_any_ko:
            return "DRAW"
        if p1_any_ko:
            return "P2"
        if p2_any_ko:
            return "P1"

        # Timeout
        timer = info.get("timer", 99)
        if timer <= 0:
            p1_total = sum(state.p1_team_health)
            p2_total = sum(state.p2_team_health)
            if p1_total > p2_total:
                return "P1"
            elif p2_total > p1_total:
                return "P2"
            else:
                return "DRAW"

        return False

    def is_match_over(
        self,
        info: dict,
        round_history: list[dict],
        *,
        state: TeamMatchState | None = None,
        match_format: int = 3,
    ) -> str | bool:
        """Standard best-of-N at match level."""
        wins_needed = (match_format // 2) + 1
        p1_wins = sum(1 for r in round_history if r.get("winner") == "P1")
        p2_wins = sum(1 for r in round_history if r.get("winner") == "P2")

        if p1_wins >= wins_needed:
            return "P1"
        if p2_wins >= wins_needed:
            return "P2"
        return False
