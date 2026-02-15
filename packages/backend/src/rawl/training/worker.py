from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from rawl.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="rawl.training.worker.run_training", bind=True)
def run_training(self, job_id: str):
    """Celery task: run PPO training pipeline."""
    import asyncio
    asyncio.run(_run_training_async(job_id))


async def _run_training_async(job_id: str):
    from rawl.db.session import async_session_factory
    from rawl.db.models.training_job import TrainingJob
    from rawl.db.models.fighter import Fighter
    from rawl.training.pipeline import create_ppo_config
    from rawl.redis_client import redis_pool
    from rawl.s3_client import upload_bytes
    from sqlalchemy import select
    from datetime import datetime, timezone

    import diambra.arena
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback

    async with async_session_factory() as db:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error("Training job not found", extra={"job_id": job_id})
            return

        # Get fighter for game_id
        result = await db.execute(select(Fighter).where(Fighter.id == job.fighter_id))
        fighter = result.scalar_one_or_none()
        if not fighter:
            logger.error("Fighter not found", extra={"job_id": job_id})
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.gpu_type = job.gpu_type or "T4"
        await db.commit()

        try:
            # Create DIAMBRA environment
            env_settings = {
                "game_id": fighter.game_id,
                "frame_shape": (128, 128, 1),
                "action_space": "multi_discrete",
                "n_players": 1,
            }
            env = diambra.arena.make(fighter.game_id, env_settings)

            # Create PPO model with config
            ppo_config = create_ppo_config(fighter.game_id, job.total_timesteps)
            model = PPO(
                ppo_config["policy"],
                env,
                learning_rate=ppo_config["learning_rate"],
                n_steps=ppo_config["n_steps"],
                batch_size=ppo_config["batch_size"],
                n_epochs=ppo_config["n_epochs"],
                gamma=ppo_config["gamma"],
                gae_lambda=ppo_config["gae_lambda"],
                clip_range=ppo_config["clip_range"],
                ent_coef=ppo_config["ent_coef"],
                vf_coef=ppo_config["vf_coef"],
                max_grad_norm=ppo_config["max_grad_norm"],
                verbose=0,
            )

            # Progress callback: publish to Redis stream every 10K steps
            class ProgressCallback(BaseCallback):
                def __init__(self, job_id: str, total: int):
                    super().__init__()
                    self._job_id = job_id
                    self._total = total
                    self._last_publish = 0

                def _on_step(self) -> bool:
                    current = self.num_timesteps
                    if current - self._last_publish >= 10_000:
                        self._last_publish = current
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            loop.run_until_complete(self._publish_progress(current))
                        except RuntimeError:
                            asyncio.run(self._publish_progress(current))
                    return True

                async def _publish_progress(self, current: int):
                    try:
                        await redis_pool.stream_publish(
                            f"training:{self._job_id}:progress",
                            {
                                "job_id": self._job_id,
                                "current_timesteps": str(current),
                                "total_timesteps": str(self._total),
                                "progress": str(round(current / self._total, 4)),
                            },
                        )
                        # Also update DB
                        async with async_session_factory() as sess:
                            res = await sess.execute(
                                select(TrainingJob).where(TrainingJob.id == self._job_id)
                            )
                            j = res.scalar_one_or_none()
                            if j:
                                j.current_timesteps = current
                                await sess.commit()
                    except Exception:
                        pass

            callback = ProgressCallback(job_id, job.total_timesteps)

            # Train
            logger.info("Training started", extra={"job_id": job_id, "game_id": fighter.game_id})
            model.learn(total_timesteps=job.total_timesteps, callback=callback)

            # Save model to temp file then upload to S3
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                model_path = tmp.name
            model.save(model_path)

            model_bytes = Path(model_path).read_bytes()
            s3_key = f"models/{fighter.id}/{job_id}.zip"
            await upload_bytes(s3_key, model_bytes, "application/zip")
            Path(model_path).unlink(missing_ok=True)

            # Update job and fighter
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.current_timesteps = job.total_timesteps
            job.model_path = s3_key

            fighter.model_path = s3_key
            await db.commit()

            env.close()
            logger.info("Training completed", extra={"job_id": job_id, "s3_key": s3_key})

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.exception("Training failed", extra={"job_id": job_id})
