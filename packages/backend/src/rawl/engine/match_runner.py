from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import asdict

import numpy as np

from rawl.config import settings
from rawl.engine.emulation.retro_engine import RetroEngine
from rawl.engine.field_validator import FieldValidator
from rawl.engine.frame_processor import encode_mjpeg_frame, preprocess_for_inference
from rawl.engine.match_result import MatchResult, compute_match_hash, resolve_tiebreaker
from rawl.engine.model_loader import load_fighter_model
from rawl.engine.oracle_client import oracle_client
from rawl.engine.replay_recorder import ReplayRecorder
from rawl.game_adapters import get_adapter
from rawl.game_adapters.errors import AdapterValidationError
from rawl.monitoring.metrics import match_duration_seconds, matches_active, matches_total
from rawl.redis_client import redis_pool
from rawl.s3_client import upload_bytes

logger = logging.getLogger(__name__)

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = settings.heartbeat_interval_seconds
# Data channel publish rate (every N frames at streaming_fps to achieve ~10Hz)
DATA_PUBLISH_INTERVAL = settings.streaming_fps // settings.data_channel_hz
# Frame stacking depth (must match training VecFrameStack n_stack)
FRAME_STACK_N = 4
# Frame skipping: step emulator N times per inference call
FRAME_SKIP = settings.frame_skip
# Wall-clock budget for one batch of N frames
BATCH_BUDGET = FRAME_SKIP / settings.streaming_fps


async def run_match(
    match_id: str,
    game_id: str,
    fighter_a_model_path: str,
    fighter_b_model_path: str,
    match_format: int = 3,
    calibration: bool = False,
) -> MatchResult | None:
    """Execute a full match per SDD Appendix A game loop.

    Returns MatchResult on success, None on cancellation/failure.
    """
    start_time = time.monotonic()
    matches_active.inc()
    logger.info(
        "Starting match",
        extra={"match_id": match_id, "game_id": game_id, "format": match_format, "frame_skip": FRAME_SKIP},
    )

    adapter = get_adapter(game_id)
    field_validator = FieldValidator(
        match_id=match_id,
        required_fields=adapter.required_fields,
    )
    recorder = ReplayRecorder(match_id)
    engine = RetroEngine(game_id, match_id)

    action_log: list = []
    round_history: list[dict] = []
    match_result: str | bool = False
    match_locked = False
    frame_count = 0
    last_heartbeat = time.monotonic()

    try:
        # Step 1: Load fighter models
        logger.info("Loading fighter models", extra={"match_id": match_id})
        model_a = await load_fighter_model(fighter_a_model_path, game_id)
        model_b = await load_fighter_model(fighter_b_model_path, game_id)

        # Step 2: Start emulation engine
        logger.info("Starting emulation engine", extra={"match_id": match_id})
        obs, info = engine.start()

        # Step 3: Validate info on first frame BEFORE lock_match
        try:
            adapter.validate_info(info)
        except AdapterValidationError as e:
            logger.error(
                "Adapter validation failed",
                extra={"match_id": match_id, "error": str(e)},
            )
            if not calibration:
                await oracle_client.submit_cancel(match_id, reason="validation_failed")
            return None

        # Validation passed — lock the match
        if not calibration:
            await oracle_client.submit_lock(match_id)
            # Publish initial heartbeat immediately after lock
            await redis_pool.set_with_expiry(
                f"heartbeat:match:{match_id}",
                str(int(time.time())),
                ex=60,
            )
            last_heartbeat = time.monotonic()
        match_locked = True

        # Detect model observation space to adapt preprocessing
        obs_shape_a = model_a.observation_space.shape
        obs_shape_b = model_b.observation_space.shape
        logger.info(
            "Model obs spaces",
            extra={"model_a": obs_shape_a, "model_b": obs_shape_b},
        )

        # Determine if frame stacking is needed per model.
        # CHW models (e.g. 3x100x128) don't use frame stacking.
        # HWC single-channel models (e.g. 84x84x1) need frame stacking.
        use_stack_a = len(obs_shape_a) == 3 and obs_shape_a[0] not in (1, 3)
        use_stack_b = len(obs_shape_b) == 3 and obs_shape_b[0] not in (1, 3)
        # For stacked obs (84,84,4): preprocess single frame as (84,84,1)
        single_shape_a = (*obs_shape_a[:2], 1) if use_stack_a else obs_shape_a
        single_shape_b = (*obs_shape_b[:2], 1) if use_stack_b else obs_shape_b

        # Initialize frame stacking buffers (only if needed)
        if use_stack_a:
            init_frame_a = preprocess_for_inference(obs["P1"], single_shape_a)
            frame_buf_a: deque[np.ndarray] = deque(
                [init_frame_a] * FRAME_STACK_N, maxlen=FRAME_STACK_N
            )
        if use_stack_b:
            init_frame_b = preprocess_for_inference(obs["P2"], single_shape_b)
            frame_buf_b: deque[np.ndarray] = deque(
                [init_frame_b] * FRAME_STACK_N, maxlen=FRAME_STACK_N
            )

        # Step 4: Game loop (two-level: outer=inference, inner=frame skip)
        done = False
        while not done:
            batch_start = time.monotonic()

            # Preprocess observations for inference (once per batch)
            if use_stack_a:
                frame_a = preprocess_for_inference(obs["P1"], single_shape_a)
                frame_buf_a.append(frame_a)
                obs_a = np.concatenate(list(frame_buf_a), axis=-1)
            else:
                obs_a = preprocess_for_inference(obs["P1"], obs_shape_a)

            if use_stack_b:
                frame_b = preprocess_for_inference(obs["P2"], single_shape_b)
                frame_buf_b.append(frame_b)
                obs_b = np.concatenate(list(frame_buf_b), axis=-1)
            else:
                obs_b = preprocess_for_inference(obs["P2"], obs_shape_b)

            # Inference: decide actions (once per batch)
            action_a, _ = model_a.predict(obs_a, deterministic=True)
            action_b, _ = model_b.predict(obs_b, deterministic=True)
            combined_action = {"P1": action_a, "P2": action_b}

            # Step emulator FRAME_SKIP times with the same action
            for _skip_i in range(FRAME_SKIP):
                frame_count += 1

                obs, reward, terminated, truncated, info = engine.step(combined_action)
                action_log.append({"P1": action_a.tolist(), "P2": action_b.tolist()})

                state = adapter.extract_state(info)

                # Continuous field validation
                validation_errors = field_validator.check_frame(info)
                if validation_errors:
                    if not match_locked:
                        logger.error(
                            "Pre-lock validation error",
                            extra={"errors": validation_errors},
                        )
                        if not calibration:
                            await oracle_client.submit_cancel(
                                match_id, reason="field_validation"
                            )
                        return None
                    else:
                        logger.warning(
                            "Post-lock validation degraded",
                            extra={"errors": validation_errors},
                        )

                if not calibration:
                    # Publish video frame to Redis stream (every step)
                    frame_jpeg = encode_mjpeg_frame(obs["P1"])
                    await redis_pool.stream_publish_bytes(
                        f"match:{match_id}:video", "frame", frame_jpeg
                    )

                    # Publish data at 10Hz
                    if frame_count % DATA_PUBLISH_INTERVAL == 0:
                        state_dict = asdict(state)
                        state_dict["match_id"] = match_id
                        state_dict["status"] = "live"
                        await redis_pool.stream_publish(
                            f"match:{match_id}:data",
                            {k: str(v) for k, v in state_dict.items()},
                        )

                    # Record replay (every step, reuse encoded JPEG)
                    recorder.write_frame(
                        frame_jpeg,
                        asdict(state)
                        if frame_count % DATA_PUBLISH_INTERVAL == 0
                        else None,
                    )

                # Check round over (every step — don't miss transitions)
                round_result = adapter.is_round_over(info, state=state)
                if round_result:
                    round_history.append({
                        "winner": round_result,
                        "p1_health": state.p1_health,
                        "p2_health": state.p2_health,
                    })
                    match_result = adapter.is_match_over(
                        info, round_history, state=state, match_format=match_format
                    )
                    if match_result:
                        done = True
                        break

                # Check env termination
                if terminated or truncated:
                    done = True
                    break

                # Safety cap
                if frame_count >= settings.max_match_frames:
                    logger.error(
                        "Match exceeded max frames, cancelling",
                        extra={"match_id": match_id, "frames": frame_count},
                    )
                    if not calibration:
                        await oracle_client.submit_cancel(
                            match_id, reason="max_frames_exceeded"
                        )
                    return None

            # Heartbeat (once per batch, not per frame)
            if not calibration:
                now = time.monotonic()
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    await redis_pool.set_with_expiry(
                        f"heartbeat:match:{match_id}",
                        str(int(time.time())),
                        ex=60,
                    )
                    last_heartbeat = now

                # Frame pacing: sleep for remaining batch budget
                elapsed = time.monotonic() - batch_start
                if elapsed < BATCH_BUDGET:
                    await asyncio.sleep(BATCH_BUDGET - elapsed)

        # Step 5: Post-loop handling
        if not match_result:
            logger.error(f"Match {match_id} terminated without winner")
            if not calibration:
                await oracle_client.submit_cancel(match_id, reason="terminated_no_winner")
            return None

        # Step 6: Tiebreaker
        if match_result == "DRAW" or (
            round_history and round_history[-1].get("winner") == "DRAW"
        ):
            match_result = resolve_tiebreaker(round_history, match_id)

        # Step 7: Hash + S3 upload (single-pass)
        recorder.close()
        hash_payload, match_hash = compute_match_hash(
            match_id=match_id,
            winner=match_result,
            round_history=round_history,
            actions=action_log,
            adapter_version=adapter.adapter_version,
        )

        if not calibration:
            # Upload hash payload to S3 (same bytes that were hashed)
            s3_ok = await upload_bytes(
                f"hashes/{match_id}.json", hash_payload, "application/json"
            )

            # Upload replay
            replay_ok = await recorder.upload_to_s3()

            if not s3_ok:
                logger.error(
                    "S3 upload failed after retries",
                    extra={"match_id": match_id},
                )
                from rawl.engine.failed_upload_handler import persist_failed_upload
                await persist_failed_upload(match_id, f"hashes/{match_id}.json", hash_payload)
                return None

        # Step 8: Build result + submit to oracle
        result = MatchResult(
            match_id=match_id,
            winner=match_result,
            round_history=round_history,
            match_hash=match_hash,
            adapter_version=adapter.adapter_version,
            hash_version=2,
            hash_payload=hash_payload,
        )
        if not calibration:
            await oracle_client.submit_resolve(match_id, match_result, match_hash)

        matches_total.labels(game_id=game_id, status="completed").inc()
        return result

    except Exception:
        logger.exception("Match execution failed", extra={"match_id": match_id})
        matches_total.labels(game_id=game_id, status="failed").inc()
        if match_locked and not calibration:
            try:
                await oracle_client.submit_cancel(match_id, reason="engine_exception")
            except Exception:
                logger.exception("Failed to cancel match after error")
        return None
    finally:
        matches_active.dec()
        duration = time.monotonic() - start_time
        match_duration_seconds.labels(game_id=game_id).observe(duration)
        recorder.close()
        recorder.cleanup()
        engine.stop()
        logger.info(
            "Match finished",
            extra={
                "match_id": match_id,
                "duration_s": round(duration, 2),
                "frames": frame_count,
            },
        )
