from __future__ import annotations

from rawl.game_adapters.base import GameAdapter, TeamMatchState


class KOF98Adapter(GameAdapter):
    """King of Fighters 98 adapter — 3v3 team elimination."""

    game_id = "kof98"
    adapter_version = "1.0.0"
    required_fields = [
        "health", "active_character",
        "char_0_health", "char_1_health", "char_2_health",
        "stage_side",
    ]

    TEAM_SIZE = 3
    MAX_HEALTH = 103
    DIRECTIONAL_INDICES = {"left": 6, "right": 7}

    def _extract_team_health(self, info: dict, player: str) -> list[float]:
        """Extract and normalize health for all 3 characters."""
        team = []
        for i in range(self.TEAM_SIZE):
            key = f"char_{i}_health"
            health = info[player].get(key, 0)
            team.append(max(0.0, health / self.MAX_HEALTH))
        return team

    def extract_state(self, info: dict) -> TeamMatchState:
        p1_team = self._extract_team_health(info, "P1")
        p2_team = self._extract_team_health(info, "P2")
        p1_active = info["P1"].get("active_character", 0)
        p2_active = info["P2"].get("active_character", 0)

        return TeamMatchState(
            p1_health=p1_team[p1_active] if p1_active < len(p1_team) else 0.0,
            p2_health=p2_team[p2_active] if p2_active < len(p2_team) else 0.0,
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
        """In KOF98, a 'round' is an elimination of one character."""
        p1_health = info["P1"].get("health", 0)
        p2_health = info["P2"].get("health", 0)
        timer = info.get("timer", 99)

        if p1_health <= 0 and p2_health <= 0:
            return "DRAW"
        if p1_health <= 0:
            return "P2"
        if p2_health <= 0:
            return "P1"

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
        state: TeamMatchState | None = None,
        match_format: int = 3,
    ) -> str | bool:
        """Match ends when all 3 characters on one side are eliminated.

        match_format is accepted for interface consistency but ignored.
        """
        if state is None:
            state = self.extract_state(info)

        p1_alive = sum(1 for h in state.p1_team_health if h > 0.0)
        p2_alive = sum(1 for h in state.p2_team_health if h > 0.0)

        if p2_alive == 0:
            return "P1"
        if p1_alive == 0:
            return "P2"
        return False
