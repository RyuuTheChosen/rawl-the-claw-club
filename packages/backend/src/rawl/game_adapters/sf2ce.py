from __future__ import annotations

from rawl.game_adapters.base import GameAdapter, MatchState


class SF2CEAdapter(GameAdapter):
    """Street Fighter II: Special Champion Edition (Genesis) adapter.

    Round detection uses matches_won / enemy_matches_won delta tracking
    rather than health checks because:
      - SF2 Genesis doesn't expose the round timer (continuetimer is the
        post-loss continue countdown, always 0 during gameplay)
      - Health stays at -1 for ~600 transition frames between rounds,
        which would cause duplicate round detections
    """

    game_id = "sf2ce"
    adapter_version = "1.0.0"
    required_fields = ["health", "round_wins"]

    MAX_HEALTH = 176

    def __init__(self) -> None:
        self._prev_p1_wins: int = 0
        self._prev_p2_wins: int = 0

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
        """Detect round end via matches_won delta.

        The emulator increments matches_won / enemy_matches_won when a
        round is won.  We fire exactly once per increment, avoiding the
        600-frame transition window where health stays at -1.
        """
        p1_wins = info["P1"].get("round_wins", 0)
        p2_wins = info["P2"].get("round_wins", 0)

        if p1_wins > self._prev_p1_wins:
            self._prev_p1_wins = p1_wins
            return "P1"
        if p2_wins > self._prev_p2_wins:
            self._prev_p2_wins = p2_wins
            return "P2"

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
