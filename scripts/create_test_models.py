#!/usr/bin/env python3
"""Create minimal SB3 PPO models and upload to MinIO for integration testing.

Creates two untrained PPO models with the correct architecture:
  - Obs space:   Box(0, 255, (84, 84, 4), uint8)  — matches frame-stacked inference
  - Action space: MultiBinary(12)                   — 12 buttons per player
  - Policy:       CnnPolicy

Usage (WSL2):
    python3 scripts/create_test_models.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from stable_baselines3 import PPO

# Add backend to path for S3 client
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "backend" / "src"))


class DummyFightEnv(gym.Env):
    """Minimal env matching the Rawl inference pipeline obs/action spaces."""

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(84, 84, 4), dtype=np.uint8
        )
        self.action_space = spaces.MultiBinary(12)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self.observation_space.sample(), {}

    def step(self, action):
        obs = self.observation_space.sample()
        return obs, 0.0, False, False, {}


def create_model(name: str, work_dir: Path) -> Path:
    """Create a dummy PPO model and save it."""
    print(f"  Creating model: {name}")
    env = DummyFightEnv()
    model = PPO("CnnPolicy", env, verbose=0, n_steps=64, batch_size=64)
    path = work_dir / f"{name}.zip"
    model.save(str(path))
    size_kb = path.stat().st_size / 1024
    print(f"  Saved: {path} ({size_kb:.0f} KB)")
    return path


async def upload_models(paths: list[tuple[str, Path]]) -> None:
    """Upload model files to MinIO."""
    # Detect Windows host IP for WSL2 -> Docker connectivity
    win_host = os.environ.get("WIN_HOST")
    if not win_host:
        try:
            with open("/etc/resolv.conf") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        win_host = line.split()[1]
                        break
        except FileNotFoundError:
            win_host = "localhost"

    os.environ.setdefault("S3_ENDPOINT", f"http://{win_host}:9000")
    os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
    os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
    os.environ.setdefault("S3_BUCKET", "rawl-replays")

    from rawl.s3_client import ensure_bucket, upload_bytes

    await ensure_bucket()

    for s3_key, local_path in paths:
        data = local_path.read_bytes()
        ok = await upload_bytes(s3_key, data, "application/zip")
        status = "OK" if ok else "FAILED"
        print(f"  Upload {s3_key}: {status} ({len(data) / 1024:.0f} KB)")


def main():
    print("=== Creating test models ===\n")

    with tempfile.TemporaryDirectory(prefix="rawl_models_") as work_dir:
        work_path = Path(work_dir)

        model_a_path = create_model("test_fighter_a", work_path)
        model_b_path = create_model("test_fighter_b", work_path)

        print("\n=== Uploading to MinIO ===\n")
        asyncio.run(
            upload_models(
                [
                    ("models/test_fighter_a.zip", model_a_path),
                    ("models/test_fighter_b.zip", model_b_path),
                ]
            )
        )

    print("\nDone! Models available at:")
    print("  s3://rawl-replays/models/test_fighter_a.zip")
    print("  s3://rawl-replays/models/test_fighter_b.zip")


if __name__ == "__main__":
    main()
