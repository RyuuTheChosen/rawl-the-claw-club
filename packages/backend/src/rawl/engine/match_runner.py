from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import asdict
from datetime import UTC, datetime

import numpy as np

from rawl.config import settings
from rawl.engine.emulation.retro_engine import RetroEngine
from rawl.engine.field_validator import FieldValidator
from rawl.engine.frame_processor import encode_mjpeg_frame, preprocess_for_inference
from rawl.engine.h264_encoder import H264Encoder, H264EncoderError
from rawl.engine.match_result import MatchResult, compute_match_hash, resolve_tiebreaker
from rawl.engine.model_loader import load_fighter_model
from rawl.engine.oracle_client import oracle_client
from rawl.engine.replay_recorder import ReplayRecorder
from rawl.game_adapters import get_adapter
from rawl.game_adapters.base import GameAdapter, MatchState
from rawl.game_adapters.errors import AdapterValidationError
from rawl.monitoring.metrics import match_duration_seconds, matches_active, matches_total
from rawl.redis_client import redis_pool
from rawl.s3_client import upload_bytes

logger = logging.getLogger(__name__)

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = settings.heartbeat_interval_seconds
# Data recorded at 10Hz (every N frames); used by recorder, not for streaming
DATA_RECORD_INTERVAL = max(1, settings.streaming_fps // settings.data_channel_hz)
# Frame stacking depth (must match training VecFrameStack n_stack)
FRAME_STACK_N = 4
# Frame skipping: step emulator N times per inference call
FRAME_SKIP = settings.frame_skip
# Per-button flip probability for match variety (epsilon-greedy noise)
ACTION_NOISE_PROB = 0.02


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
    engine = RetroEngine(game_id, match_id, adapter=adapter)

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

        # Seeded RNG for reproducible action noise (match variety)
        match_rng = np.random.RandomState(
            int(hashlib.sha256(match_id.encode()).hexdigest()[:8], 16)
        )

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
        lock_time = datetime.now(UTC)

        # Start live H.264 encoder (if enabled and not calibrating)
        encoder: H264Encoder | None = None
        if not calibration and settings.live_streaming_enabled:
            try:
                encoder = H264Encoder(
                    match_id, settings.live_stream_width, settings.live_stream_height
                )
                await encoder.start()
                logger.info("Live H.264 encoder started", extra={"match_id": match_id})
            except H264EncoderError:
                logger.warning(
                    "Live streaming unavailable, continuing with replay-only",
                    extra={"match_id": match_id},
                )
                encoder = None

        # Detect model observation space to adapt preprocessing
        obs_shape_a = model_a.observation_space.shape
        obs_shape_b = model_b.observation_space.shape
        logger.info(
            "Model obs spaces",
            extra={"model_a": obs_shape_a, "model_b": obs_shape_b},
        )

        # SB3 CnnPolicy stores obs in CHW format (VecTransposeImage auto-applied).
        # VecFrameStack(n_stack=4) on (1,84,84) produces (4,84,84).
        # VecFrameStack(n_stack=4) on (3,84,84) produces (12,84,84).
        # Channel dim is always dim 0 in CHW.
        def _detect_stacking(obs_shape: tuple[int, ...]) -> tuple[bool, tuple[int, ...], int]:
            """Returns (use_stack, single_frame_shape, stack_axis)."""
            if len(obs_shape) != 3:
                return False, obs_shape, 0
            n_ch = obs_shape[0]
            if n_ch in (1, 3):
                return False, obs_shape, 0  # Single grayscale or RGB, no stacking
            if n_ch == FRAME_STACK_N:
                # 4 channels = 4 stacked grayscale
                return True, (1, obs_shape[1], obs_shape[2]), 0
            if n_ch > FRAME_STACK_N and n_ch % FRAME_STACK_N == 0:
                # e.g. 12 = 4 stacked RGB (base_channels = 3)
                base_ch = n_ch // FRAME_STACK_N
                return True, (base_ch, obs_shape[1], obs_shape[2]), 0
            # Unknown channel count — treat as non-stacked
            return False, obs_shape, 0

        use_stack_a, single_shape_a, stack_axis_a = _detect_stacking(obs_shape_a)
        use_stack_b, single_shape_b, stack_axis_b = _detect_stacking(obs_shape_b)

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
            # Preprocess observations for inference (once per batch)
            if use_stack_a:
                frame_a = preprocess_for_inference(obs["P1"], single_shape_a)
                frame_buf_a.append(frame_a)
                obs_a = np.concatenate(list(frame_buf_a), axis=stack_axis_a)
            else:
                obs_a = preprocess_for_inference(obs["P1"], obs_shape_a)

            if use_stack_b:
                frame_b = preprocess_for_inference(obs["P2"], single_shape_b)
                frame_buf_b.append(frame_b)
                obs_b = np.concatenate(list(frame_buf_b), axis=stack_axis_b)
            else:
                obs_b = preprocess_for_inference(obs["P2"], obs_shape_b)

            # Inference: decide actions (once per batch)
            action_a, _ = model_a.predict(obs_a, deterministic=True)
            action_b, _ = model_b.predict(obs_b, deterministic=True)
            # Epsilon-greedy noise: flip each button with small probability for
            # match variety while keeping inference fast (deterministic=True).
            # Seeded by match_id so results are reproducible for hash verification.
            noise_a = match_rng.random(action_a.shape) < ACTION_NOISE_PROB
            noise_b = match_rng.random(action_b.shape) < ACTION_NOISE_PROB
            action_a = np.where(noise_a, 1 - action_a, action_a)
            action_b = np.where(noise_b, 1 - action_b, action_b)
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
                    raw_frame = obs["P1"]

                    # Feed to live encoder (if active)
                    if encoder and encoder.is_running:
                        try:
                            await encoder.feed_frame(raw_frame)
                        except (H264EncoderError, ValueError):
                            logger.warning(
                                "Encoder feed failed, disabling live stream",
                                extra={"match_id": match_id},
                            )
                            encoder = None  # Continue with replay-only

                    # Record MJPEG for post-match replay (always)
                    frame_jpeg = encode_mjpeg_frame(raw_frame)
                    state_dict = None
                    if frame_count % DATA_RECORD_INTERVAL == 0:
                        state_dict = asdict(state)
                        state_dict["has_round_timer"] = adapter.has_round_timer
                        # Publish to live data stream
                        if encoder and encoder.is_running:
                            await _publish_live_data(match_id, state, adapter, frame_count)
                    recorder.write_frame(frame_jpeg, state_dict)

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

                # Per-frame pacing for smooth live delivery (drift-corrected).
                # Must be inside the inner loop so each frame is individually
                # spaced at ~16.7ms, preventing burst delivery to the frontend.
                if encoder and encoder.is_running:
                    target_time = start_time + (frame_count / settings.streaming_fps)
                    sleep_time = target_time - time.monotonic()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

            # Heartbeat + progress log (once per batch, not per frame)
            if not calibration:
                now = time.monotonic()
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    await redis_pool.set_with_expiry(
                        f"heartbeat:match:{match_id}",
                        str(int(time.time())),
                        ex=60,
                    )
                    last_heartbeat = now
                    elapsed_total = now - start_time
                    logger.info(
                        "Match progress",
                        extra={
                            "match_id": match_id,
                            "frames": frame_count,
                            "elapsed_s": round(elapsed_total, 1),
                            "fps": round(frame_count / elapsed_total, 1) if elapsed_total > 0 else 0,
                            "rounds": len(round_history),
                        },
                    )
            # When encoder is None/stopped, runs at max speed (same as before)

        # Step 5: Post-loop handling — stop live encoder
        if encoder:
            # Signal match end to live viewers via data channel
            try:
                winner_side = 1 if match_result == "P1" else (2 if match_result == "P2" else 0)
                await redis_pool.stream_publish(
                    f"match:{match_id}:data",
                    {b"status": b"ended", b"match_winner": str(winner_side).encode()},
                    maxlen=settings.redis_data_stream_maxlen,
                )
            except Exception:
                logger.warning("Failed to publish match-end signal")
            await encoder.stop()
            encoder = None

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
            if not replay_ok:
                logger.error(
                    "Replay upload failed",
                    extra={"match_id": match_id},
                )
                from rawl.engine.failed_upload_handler import persist_failed_upload
                await persist_failed_upload(
                    match_id, f"replays/{match_id}.mjpeg", payload=None
                )

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
            replay_uploaded=replay_ok if not calibration else True,
            locked_at=lock_time if match_locked else None,
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
        if encoder:
            try:
                await encoder.stop()
            except Exception:
                logger.exception("Failed to stop encoder in cleanup")
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


async def _publish_live_data(
    match_id: str,
    state: MatchState,
    adapter: GameAdapter,
    frame_count: int,
) -> None:
    """Publish game state to Redis data stream for live viewers.

    Errors are logged and swallowed — data drops are acceptable.
    """
    data: dict[bytes, bytes] = {
        b"timestamp": str(time.time()).encode(),
        b"p1_health": str(state.p1_health).encode(),
        b"p2_health": str(state.p2_health).encode(),
        b"round_number": str(state.round_number).encode(),
        b"timer": str(state.timer).encode(),
        b"status": b"live",
        b"has_round_timer": str(int(adapter.has_round_timer)).encode(),
        b"frame": str(frame_count).encode(),
    }
    # Team game fields (KOF98, Tekken Tag)
    if hasattr(state, "p1_team_health"):
        data[b"p1_team_health"] = str(state.p1_team_health).encode()
        data[b"p2_team_health"] = str(state.p2_team_health).encode()
        data[b"p1_active_character"] = str(state.p1_active_character).encode()
        data[b"p2_active_character"] = str(state.p2_active_character).encode()
    try:
        await redis_pool.stream_publish(
            f"match:{match_id}:data", data, maxlen=settings.redis_data_stream_maxlen
        )
    except Exception:
        logger.debug("Failed to publish live data", extra={"match_id": match_id})
