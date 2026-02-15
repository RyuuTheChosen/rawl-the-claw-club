"""Model loader: download SB3 models from S3 and cache in memory."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from stable_baselines3 import PPO

from rawl.s3_client import download_bytes

logger = logging.getLogger(__name__)

# In-memory cache by S3 key
_model_cache: dict[str, PPO] = {}


async def load_fighter_model(s3_key: str, game_id: str) -> PPO:
    """Download a fighter model from S3 and load it with SB3.

    Models are cached in memory by S3 key to avoid re-downloading
    for matches with the same fighter.

    Args:
        s3_key: S3 path to the .zip model file
        game_id: Game identifier for action space validation

    Returns:
        Loaded SB3 PPO model

    Raises:
        RuntimeError: If download or load fails
    """
    # Check cache
    if s3_key in _model_cache:
        logger.info("Model cache hit", extra={"s3_key": s3_key})
        return _model_cache[s3_key]

    # Download from S3
    logger.info("Downloading model from S3", extra={"s3_key": s3_key})
    model_bytes = await download_bytes(s3_key)
    if model_bytes is None:
        raise RuntimeError(f"Failed to download model: {s3_key}")

    # Save to temp file for SB3 loading
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(model_bytes)
        tmp_path = tmp.name

    try:
        model = PPO.load(tmp_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load model {s3_key}: {e}") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Cache and return
    _model_cache[s3_key] = model
    logger.info("Model loaded and cached", extra={"s3_key": s3_key})
    return model


def clear_cache() -> None:
    """Clear the model cache (for testing or memory management)."""
    _model_cache.clear()
