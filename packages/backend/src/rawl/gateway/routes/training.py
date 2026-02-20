from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func

from rawl.config import settings
from rawl.db.models.fighter import Fighter
from rawl.db.models.training_job import TrainingJob
from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.gateway.auth import ApiKeyAuth
from rawl.gateway.schemas import TrainRequest, TrainResponse, TrainingStatusResponse

router = APIRouter(tags=["gateway-training"])

# Training tier limits
TIER_LIMITS = {
    "free": {
        "max_timesteps": settings.training_tier_free_timesteps,
        "gpu_type": settings.training_tier_free_gpu,
        "max_concurrent": settings.training_max_concurrent_free,
    },
    "standard": {
        "max_timesteps": settings.training_tier_standard_timesteps,
        "gpu_type": settings.training_tier_standard_gpu,
        "max_concurrent": settings.training_max_concurrent_standard,
    },
    "pro": {
        "max_timesteps": settings.training_tier_pro_timesteps,
        "gpu_type": settings.training_tier_pro_gpu,
        "max_concurrent": settings.training_max_concurrent_pro,
    },
}


@router.post("/train", response_model=TrainResponse, status_code=201)
async def start_training(
    request: Request,
    db: DbSession,
    wallet: ApiKeyAuth,
    body: TrainRequest,
):
    """Start a training job for a fighter."""
    # Verify fighter ownership
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(Fighter.id == body.fighter_id, Fighter.owner_id == user.id)
    )
    fighter = result.scalar_one_or_none()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found or not owned by you")

    # Validate tier
    tier = body.tier if hasattr(body, "tier") and body.tier else "free"
    tier_config = TIER_LIMITS.get(tier)
    if not tier_config:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")

    # Check timestep limit
    if body.total_timesteps > tier_config["max_timesteps"]:
        raise HTTPException(
            status_code=400,
            detail=f"Tier '{tier}' max timesteps: {tier_config['max_timesteps']}",
        )

    # Check concurrent job limit
    concurrent_result = await db.execute(
        select(func.count()).select_from(TrainingJob).where(
            TrainingJob.owner_id == user.id,
            TrainingJob.status.in_(["queued", "running"]),
        )
    )
    concurrent = concurrent_result.scalar() or 0
    if concurrent >= tier_config["max_concurrent"]:
        raise HTTPException(
            status_code=429,
            detail=f"Concurrent job limit reached ({tier_config['max_concurrent']} for {tier} tier)",
        )

    job = TrainingJob(
        fighter_id=body.fighter_id,
        owner_id=user.id,
        algorithm=body.algorithm,
        total_timesteps=body.total_timesteps,
        tier=tier,
        gpu_type=tier_config["gpu_type"],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Kick off training task via ARQ (always raises NotImplementedError — off-platform)
    await request.app.state.arq_pool.enqueue_job("run_training", str(job.id))

    return TrainResponse(job_id=job.id, status=job.status)


@router.get("/train/{job_id}", response_model=TrainingStatusResponse)
async def get_training_status(
    db: DbSession,
    wallet: ApiKeyAuth,
    job_id: uuid.UUID,
):
    """Get training job status."""
    # Verify ownership
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(TrainingJob).where(
            TrainingJob.id == job_id,
            TrainingJob.owner_id == user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    return TrainingStatusResponse(
        job_id=job.id,
        status=job.status,
        current_timesteps=job.current_timesteps,
        total_timesteps=job.total_timesteps,
        reward=job.reward,
        error_message=job.error_message,
    )


@router.post("/train/{job_id}/stop")
async def stop_training(
    db: DbSession,
    wallet: ApiKeyAuth,
    job_id: uuid.UUID,
):
    """Stop a running training job."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(TrainingJob).where(
            TrainingJob.id == job_id,
            TrainingJob.owner_id == user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    if job.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot stop job with status: {job.status}")

    from datetime import datetime, timezone

    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {"job_id": str(job.id), "status": "cancelled"}
