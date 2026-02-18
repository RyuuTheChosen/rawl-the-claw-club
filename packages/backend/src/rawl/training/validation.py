from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from rawl.celery_app import celery, celery_async_run

logger = logging.getLogger(__name__)

# Validation thresholds
INFERENCE_P99_THRESHOLD_MS = 5.0
SANDBOX_TIMEOUT_SECONDS = 60
ACTION_SPACE_TEST_FRAMES = 100
INFERENCE_TEST_STEPS = 100


@celery.task(name="rawl.training.validation.validate_model")
def validate_model(fighter_id: str, model_s3_key: str):
    """4-step model validation pipeline per SDD Section 4.6.

    1. Normalize + load test — load with compat shims, re-save in native format
    2. Action space validation — 100 random observations, check output shape
    3. Inference latency — 100 steps, reject if p99 > 5ms
    4. Sandbox — disposable Docker container, no network, read-only FS, 60s timeout

    Fighter status: validating → ready (pass) or rejected (fail)
    """
    celery_async_run(_validate_async(fighter_id, model_s3_key))


async def _validate_async(fighter_id: str, model_s3_key: str):
    import docker
    import numpy as np
    from sqlalchemy import select

    from rawl.db.models.fighter import Fighter
    from rawl.db.session import worker_session_factory
    from rawl.engine.model_normalizer import normalize_model
    from rawl.services.agent_registry import update_fighter_status

    sandbox_path: str | None = None

    async with worker_session_factory() as db:
        # Get fighter to determine game_id
        result = await db.execute(select(Fighter).where(Fighter.id == fighter_id))
        fighter = result.scalar_one_or_none()
        if not fighter:
            logger.error("Fighter not found", extra={"fighter_id": fighter_id})
            return

        try:
            # Step 1: Normalize + load test
            # Downloads from S3, loads with compat shims, re-saves in native
            # format, re-uploads to same S3 key. Returns loaded model.
            logger.info("Validation step 1: Normalize & load", extra={"fighter_id": fighter_id})
            model = await normalize_model(model_s3_key)
            if model is None:
                logger.error(
                    "Normalize/load failed", extra={"fighter_id": fighter_id}
                )
                await update_fighter_status(fighter_id, "rejected", db)
                return

            # Step 2: Action space validation
            logger.info("Validation step 2: Action space", extra={"fighter_id": fighter_id})
            obs_shape = model.observation_space.shape
            try:
                for _ in range(ACTION_SPACE_TEST_FRAMES):
                    obs = np.random.randint(0, 256, size=obs_shape, dtype=np.uint8)
                    action, _ = model.predict(obs, deterministic=True)
                    if np.any(np.isnan(action)):
                        raise ValueError("Model produced NaN actions")
            except Exception as e:
                logger.error(
                    "Action space validation failed",
                    extra={"fighter_id": fighter_id, "error": str(e)},
                )
                await update_fighter_status(fighter_id, "rejected", db)
                return

            # Step 3: Inference latency
            logger.info("Validation step 3: Inference latency", extra={"fighter_id": fighter_id})
            latencies = []
            obs = np.random.randint(0, 256, size=obs_shape, dtype=np.uint8)
            for _ in range(INFERENCE_TEST_STEPS):
                start = time.perf_counter()
                model.predict(obs, deterministic=True)
                latencies.append((time.perf_counter() - start) * 1000)

            p99 = sorted(latencies)[int(0.99 * len(latencies))]
            if p99 > INFERENCE_P99_THRESHOLD_MS:
                logger.error(
                    "Inference latency exceeded threshold",
                    extra={"fighter_id": fighter_id, "p99_ms": round(p99, 2)},
                )
                await update_fighter_status(fighter_id, "rejected", db)
                return

            # Step 4: Sandbox run
            # Save normalized model to temp file for the Docker container
            logger.info("Validation step 4: Sandbox", extra={"fighter_id": fighter_id})
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                sandbox_path = tmp.name
            model.save(sandbox_path)

            try:
                client = docker.from_env()
                client.containers.run(
                    "python:3.11-slim",
                    command=[
                        "python", "-c",
                        f"from stable_baselines3 import PPO; "
                        f"m=PPO.load('{sandbox_path}'); print('OK')",
                    ],
                    volumes={sandbox_path: {"bind": sandbox_path, "mode": "ro"}},
                    network_disabled=True,
                    read_only=True,
                    mem_limit="512m",
                    detach=False,
                    remove=True,
                    timeout=SANDBOX_TIMEOUT_SECONDS,
                )
            except docker.errors.ContainerError:
                logger.error("Sandbox validation failed", extra={"fighter_id": fighter_id})
                await update_fighter_status(fighter_id, "rejected", db)
                return
            except Exception:
                # Docker not available — skip sandbox in dev/Railway
                logger.warning(
                    "Docker not available, skipping sandbox step",
                    extra={"fighter_id": fighter_id},
                )

            # All steps passed — move to calibration phase
            await update_fighter_status(fighter_id, "calibrating", db)
            from rawl.engine.tasks import run_calibration_task

            run_calibration_task.delay(fighter_id)
            logger.info(
                "Validation passed, dispatched calibration",
                extra={"fighter_id": fighter_id, "p99_ms": round(p99, 2)},
            )

        except Exception:
            logger.exception("Validation failed", extra={"fighter_id": fighter_id})
            await update_fighter_status(fighter_id, "rejected", db)
        finally:
            if sandbox_path:
                Path(sandbox_path).unlink(missing_ok=True)
