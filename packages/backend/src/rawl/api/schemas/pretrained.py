from __future__ import annotations

from pydantic import BaseModel


class PretrainedModelResponse(BaseModel):
    id: str
    game_id: str
    name: str
    character: str
    description: str
