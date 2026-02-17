from __future__ import annotations

import cv2
import numpy as np


def preprocess_for_inference(
    frame_rgb: np.ndarray,
    obs_shape: tuple[int, ...] = (84, 84, 1),
) -> np.ndarray:
    """Convert RGB frame to the observation shape expected by a model.

    Supports two formats:
      - (H, W, 1) — grayscale, HWC (DeepMind WarpFrame style, e.g. 84x84x1)
      - (C, H, W) — RGB, CHW (PyTorch convention, e.g. 3x100x128)

    Args:
        frame_rgb: Raw RGB frame from emulator (HWC).
        obs_shape: Target shape from model.observation_space.shape.
    """
    if len(obs_shape) == 3 and obs_shape[0] in (1, 3):
        # Channels-first: (C, H, W)
        c, h, w = obs_shape
        if c == 1:
            gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            resized = cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA)
            return resized.reshape(1, h, w)
        else:
            resized = cv2.resize(frame_rgb, (w, h), interpolation=cv2.INTER_AREA)
            return np.transpose(resized, (2, 0, 1))  # HWC -> CHW
    else:
        # Channels-last: (H, W, C)
        h, w = obs_shape[0], obs_shape[1]
        c = obs_shape[2] if len(obs_shape) == 3 else 1
        if c == 1:
            gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            resized = cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA)
            return resized.reshape(h, w, 1)
        else:
            resized = cv2.resize(frame_rgb, (w, h), interpolation=cv2.INTER_AREA)
            return resized


def encode_mjpeg_frame(frame_rgb: np.ndarray, quality: int = 80) -> bytes:
    """JPEG encode a single RGB frame for MJPEG streaming.

    Args:
        frame_rgb: RGB frame as numpy array.
        quality: JPEG quality 1-100.

    Returns:
        JPEG encoded bytes.
    """
    # cv2 expects BGR
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, encoded = cv2.imencode(".jpg", frame_bgr, encode_params)
    if not success:
        raise RuntimeError("Failed to encode JPEG frame")
    return encoded.tobytes()
