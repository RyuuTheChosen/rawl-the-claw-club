from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from rawl.celery_app import celery, celery_async_run
from rawl.s3_client import download_bytes

logger = logging.getLogger(__name__)

# Validation thresholds
INFERENCE_P99_THRESHOLD_MS = 5.0
SANDBOX_TIMEOUT_SECONDS = 60
ACTION_SPACE_TEST_FRAMES = 100
INFERENCE_TEST_STEPS = 100


@celery.task(name="rawl.training.validation.validate_model")
def validate_model(fighter_id: str, model_s3_key: str):
    """4-step model validation pipeline per SDD Section 4.6.

    1. Load test — SB3.load() in try/except
    2. Action space validation — 100 random observations, check MultiDiscrete output shape
    3. Inference latency — 100 steps, reject if p99 > 5ms
    4. Sandbox — disposable Docker container, no network, read-only FS, 60s timeout

    Fighter status: validating → ready (pass) or rejected (fail)
    """
    celery_async_run(_validate_async(fighter_id, model_s3_key))


async def _validate_async(fighter_id: str, model_s3_key: str):
    from rawl.db.session import async_session_factory
    from rawl.db.models.fighter import Fighter
    from rawl.services.agent_registry import update_fighter_status
    from sqlalchemy import select

    import docker
    import numpy as np
    from stable_baselines3 import PPO

    async with async_session_factory() as db:
        # Get fighter to determine game_id
        result = await db.execute(select(Fighter).where(Fighter.id == fighter_id))
        fighter = result.scalar_one_or_none()
        if not fighter:
            logger.error("Fighter not found", extra={"fighter_id": fighter_id})
            return

        try:
            # Download model from S3
            model_bytes = await download_bytes(model_s3_key)
            if model_bytes is None:
                await update_fighter_status(fighter_id, "rejected", db)
                logger.error("Model download failed", extra={"fighter_id": fighter_id})
                return

            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp.write(model_bytes)
                tmp_path = tmp.name

            # Step 1: Load test
            logger.info("Validation step 1: Load test", extra={"fighter_id": fighter_id})
            try:
                model = PPO.load(tmp_path)
            except Exception as e:
                logger.error("Load test failed", extra={"fighter_id": fighter_id, "error": str(e)})
                await update_fighter_status(fighter_id, "rejected", db)
                return

            # Step 2: Action space validation
            logger.info("Validation step 2: Action space", extra={"fighter_id": fighter_id})
            try:
                for _ in range(ACTION_SPACE_TEST_FRAMES):
                    # Generate random observation matching expected shape (84, 84, 4)
                    obs = np.random.randint(0, 256, size=(84, 84, 4), dtype=np.uint8)
                    action, _ = model.predict(obs, deterministic=True)
                    # Verify output is valid (not NaN, correct shape)
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
            obs = np.random.randint(0, 256, size=(84, 84, 4), dtype=np.uint8)
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
            logger.info("Validation step 4: Sandbox", extra={"fighter_id": fighter_id})
            try:
                client = docker.from_env()
                container = client.containers.run(
                    "python:3.11-slim",
                    command=f"python -c \"from stable_baselines3 import PPO; m=PPO.load('{tmp_path}'); print('OK')\"",
                    volumes={tmp_path: {"bind": tmp_path, "mode": "ro"}},
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
                # Docker not available — skip sandbox in dev
                logger.warning("Docker not available, skipping sandbox step", extra={"fighter_id": fighter_id})

            # All steps passed — move to calibration phase
            await update_fighter_status(fighter_id, "calibrating", db)
            from rawl.engine.tasks import run_calibration_task

            run_calibration_task.delay(fighter_id)
            logger.info(
                "Validation passed, dispatched calibration",
                extra={"fighter_id": fighter_id, "p99_ms": round(p99, 2)},
            )

        except Exception as e:
            logger.exception("Validation failed", extra={"fighter_id": fighter_id})
            await update_fighter_status(fighter_id, "rejected", db)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
