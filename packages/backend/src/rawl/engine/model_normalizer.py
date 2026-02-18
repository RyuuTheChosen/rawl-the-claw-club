"""Model normalizer: load SB3 models with compat shims and re-save in native format.

Resolves cross-Python-version cloudpickle issues and SB3 state_dict key
migrations (features_extractor -> pi_features_extractor/vf_features_extractor).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from stable_baselines3 import PPO

from rawl.redis_client import redis_pool
from rawl.s3_client import download_bytes, upload_bytes

logger = logging.getLogger(__name__)

# Shared compat constants — single source of truth.
# Used by model_loader.py (defense-in-depth) and this module (normalization).
COMPAT_CUSTOM_OBJECTS = {
    "lr_schedule": lambda _: 0.0,
    "clip_range": lambda _: 0.0,
    "learning_rate": 0.0,
}
TRUSTED_PREFIXES = ("models/", "pretrained/", "reference/")


async def normalize_model(s3_key: str) -> PPO | None:
    """Download a model from S3, load with compat shims, re-save, and re-upload.

    The re-saved model uses the current Python/SB3 serialization format,
    eliminating cross-version cloudpickle and state_dict issues.

    Args:
        s3_key: S3 path to the model file.

    Returns:
        Loaded PPO model on success, None on failure.
    """
    if not any(s3_key.startswith(p) for p in TRUSTED_PREFIXES):
        raise RuntimeError(f"Untrusted model path: {s3_key}")

    # Distributed lock — prevent two workers normalizing the same model
    lock_key = f"normalize:{s3_key}"
    acquired = await redis_pool.set(lock_key, "1", nx=True, ex=300)
    if not acquired:
        logger.info("Normalization already in progress", extra={"s3_key": s3_key})
        return None

    logger.info("Normalizing model", extra={"s3_key": s3_key})
    tmp_in = None
    tmp_out = None

    try:
        model_bytes = await download_bytes(s3_key)
        if model_bytes is None:
            logger.error("Download failed during normalization", extra={"s3_key": s3_key})
            return None

        # Write original to temp file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(model_bytes)
            tmp_in = f.name

        # Load with compat shims — handles cross-version lambda and state_dict issues
        model = PPO.load(tmp_in, custom_objects=COMPAT_CUSTOM_OBJECTS, device="cpu")

        # Re-save in native format
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            tmp_out = f.name
        model.save(tmp_out)

        # Upload normalized model back to same S3 key
        normalized_bytes = Path(tmp_out).read_bytes()
        ok = await upload_bytes(s3_key, normalized_bytes)
        if not ok:
            logger.error("Failed to upload normalized model", extra={"s3_key": s3_key})
            return None

        logger.info(
            "Model normalized and re-uploaded",
            extra={
                "s3_key": s3_key,
                "original_size": len(model_bytes),
                "normalized_size": len(normalized_bytes),
            },
        )
        return model

    except Exception:
        logger.exception("Model normalization failed", extra={"s3_key": s3_key})
        return None
    finally:
        if tmp_in:
            Path(tmp_in).unlink(missing_ok=True)
        if tmp_out:
            Path(tmp_out).unlink(missing_ok=True)
        await redis_pool.delete(lock_key)
