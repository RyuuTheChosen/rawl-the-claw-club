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


# ---------------------------------------------------------------------------
# Input overlay — real-time button press display for live streams
# ---------------------------------------------------------------------------
# Genesis SF2 button indices (per player, 12 buttons):
#   B=0(LK), A=1(MK), MODE=2, START=3, UP=4, DOWN=5, LEFT=6, RIGHT=7,
#   C=8(HK), Y=9(LP), X=10(MP), Z=11(HP)
_OVL_UP, _OVL_DOWN, _OVL_LEFT, _OVL_RIGHT = 4, 5, 6, 7
_OVL_LP, _OVL_MP, _OVL_HP = 9, 10, 11  # Y, X, Z (punches)
_OVL_LK, _OVL_MK, _OVL_HK = 0, 1, 8   # B, A, C (kicks)

# Layout constants (for 256×256 frame)
_BTN_SZ = 12      # button square size
_BTN_GAP = 3      # gap between buttons
_BAR_H = 38       # overlay bar height (2 rows + padding)
_ROW_H = 17       # per-player row height
_LABEL_W = 18     # space for "1P"/"2P" label

# Colors (BGR — cv2 uses BGR)
_C_OFF = (50, 50, 50)           # dim gray (not pressed)
_C_DIR = (255, 255, 255)        # white (direction pressed)
_C_PUNCH = (255, 160, 40)       # cyan-blue (punch pressed)
_C_KICK = (60, 60, 255)         # red (kick pressed)
_C_LABEL = (180, 180, 180)      # light gray text
_C_BTN_TEXT = (20, 20, 20)      # dark text on bright buttons
_C_BTN_TEXT_OFF = (120, 120, 120)  # muted text on dim buttons

# Button labels for each group
_DIR_LABELS = ["<", "^", "v", ">"]
_PUNCH_LABELS = ["LP", "MP", "HP"]
_KICK_LABELS = ["LK", "MK", "HK"]


def draw_input_overlay(
    frame_rgb: np.ndarray,
    p1_action: np.ndarray,
    p2_action: np.ndarray,
) -> np.ndarray:
    """Draw button press indicators for both players at the bottom of the frame.

    Returns a copy with the overlay — does NOT modify the original (safe for inference).
    Input frame is RGB; overlay is drawn in RGB space.
    """
    out = frame_rgb.copy()
    h, w = out.shape[:2]
    bar_y = h - _BAR_H

    # Darken the overlay bar area
    out[bar_y:] = (out[bar_y:].astype(np.float32) * 0.25).astype(np.uint8)

    # P1 row (top of bar)
    _draw_player_row(out, p1_action, x0=2, y0=bar_y + 1, label="1P")
    # P2 row (bottom of bar)
    _draw_player_row(out, p2_action, x0=2, y0=bar_y + 1 + _ROW_H, label="2P")

    return out


def _draw_player_row(
    frame: np.ndarray,
    action: np.ndarray,
    x0: int,
    y0: int,
    label: str,
) -> None:
    """Draw one player's button row: label + d-pad + attack buttons."""
    cv2.putText(
        frame, label, (x0, y0 + 10),
        cv2.FONT_HERSHEY_PLAIN, 0.8, _c_rgb(_C_LABEL), 1, cv2.LINE_AA,
    )

    x = x0 + _LABEL_W

    # D-pad: ← ↑ ↓ →
    for i, btn_idx in enumerate((_OVL_LEFT, _OVL_UP, _OVL_DOWN, _OVL_RIGHT)):
        pressed = int(action[btn_idx]) > 0
        color = _c_rgb(_C_DIR) if pressed else _c_rgb(_C_OFF)
        _draw_btn(frame, x, y0, color, pressed, _DIR_LABELS[i])
        x += _BTN_SZ + _BTN_GAP

    x += _BTN_GAP * 2  # extra gap before attacks

    # Punches: LP MP HP
    for i, btn_idx in enumerate((_OVL_LP, _OVL_MP, _OVL_HP)):
        pressed = int(action[btn_idx]) > 0
        color = _c_rgb(_C_PUNCH) if pressed else _c_rgb(_C_OFF)
        _draw_btn(frame, x, y0, color, pressed, _PUNCH_LABELS[i])
        x += _BTN_SZ + _BTN_GAP

    x += _BTN_GAP * 2  # gap between punches and kicks

    # Kicks: LK MK HK
    for i, btn_idx in enumerate((_OVL_LK, _OVL_MK, _OVL_HK)):
        pressed = int(action[btn_idx]) > 0
        color = _c_rgb(_C_KICK) if pressed else _c_rgb(_C_OFF)
        _draw_btn(frame, x, y0, color, pressed, _KICK_LABELS[i])
        x += _BTN_SZ + _BTN_GAP


def _draw_btn(
    frame: np.ndarray, x: int, y: int, color: tuple, filled: bool, label: str = "",
) -> None:
    """Draw a single button indicator square with an optional text label."""
    if filled:
        cv2.rectangle(frame, (x, y), (x + _BTN_SZ, y + _BTN_SZ), color, -1)
        text_color = _c_rgb(_C_BTN_TEXT)
    else:
        cv2.rectangle(frame, (x, y), (x + _BTN_SZ, y + _BTN_SZ), color, 1)
        text_color = _c_rgb(_C_BTN_TEXT_OFF)
    if label:
        # Single char labels center nicely; 2-char labels (LP etc.) use smaller font
        font_scale = 0.45 if len(label) <= 1 else 0.35
        # Approximate centering
        text_w = int(len(label) * 4 * font_scale / 0.35)
        tx = x + (_BTN_SZ - text_w) // 2 + 1
        ty = y + _BTN_SZ - 3
        cv2.putText(
            frame, label, (tx, ty),
            cv2.FONT_HERSHEY_PLAIN, font_scale, text_color, 1, cv2.LINE_AA,
        )


def _c_rgb(bgr: tuple) -> tuple:
    """Convert BGR color tuple to RGB for drawing on an RGB frame."""
    return (bgr[2], bgr[1], bgr[0])


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
