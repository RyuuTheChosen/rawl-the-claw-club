from __future__ import annotations

import cv2
import numpy as np


def preprocess_for_inference(frame_rgb: np.ndarray) -> np.ndarray:
    """Convert RGB frame to 84x84x1 grayscale for model inference.

    Matches SB3 WarpFrame (DeepMind standard) used during training.
    """
    gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, (84, 84), interpolation=cv2.INTER_AREA)
    return resized.reshape(84, 84, 1)


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
