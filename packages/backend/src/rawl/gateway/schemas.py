from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    wallet_address: str = Field(..., min_length=32, max_length=44)
    signature: str
    message: str


class RegisterResponse(BaseModel):
    api_key: str
    wallet_address: str


class SubmitFighterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    game_id: str = Field(..., min_length=1, max_length=32)
    character: str = Field(..., min_length=1, max_length=64)
    model_s3_key: str


class FighterResponse(BaseModel):
    id: uuid.UUID
    name: str
    game_id: str
    character: str
    elo_rating: float
    matches_played: int
    wins: int
    losses: int
    status: str
    created_at: datetime


class TrainRequest(BaseModel):
    fighter_id: uuid.UUID
    algorithm: str = "PPO"
    total_timesteps: int = Field(default=1_000_000, ge=10_000, le=50_000_000)
    tier: str = Field(default="free", pattern="^(free|standard|pro)$")


class TrainResponse(BaseModel):
    job_id: uuid.UUID
    status: str


class TrainingStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    current_timesteps: int
    total_timesteps: int
    reward: float | None = None
    error_message: str | None = None


class QueueMatchRequest(BaseModel):
    fighter_id: uuid.UUID
    game_id: str
    match_type: str = "ranked"  # ranked, challenge, exhibition


class QueueMatchResponse(BaseModel):
    queued: bool
    message: str


class CreateCustomMatchRequest(BaseModel):
    fighter_a_id: uuid.UUID
    fighter_b_id: uuid.UUID
    match_format: str = Field(default="bo3", pattern="^(bo1|bo3|bo5)$")
    has_pool: bool = False
