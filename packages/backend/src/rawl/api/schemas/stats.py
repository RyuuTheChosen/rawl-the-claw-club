from __future__ import annotations

from pydantic import BaseModel


class PlatformStatsResponse(BaseModel):
    total_matches: int
    active_fighters: int
    total_volume_wei: int
    live_matches: int
