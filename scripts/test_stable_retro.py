#!/usr/bin/env python3
"""
Standalone stable-retro test — verifies the emulation layer works independently.

Run from WSL2 (stable-retro does not build on native Windows):
    wsl -d Ubuntu-22.04 -- python3 scripts/test_stable_retro.py

Requirements (WSL2):
    pip3 install stable-retro Pillow

ROM setup (one-time):
    Copy "Street Fighter II' - Special Champion Edition (U) [!].bin" as rom.md to:
    /usr/local/lib/python3.10/dist-packages/stable_retro/data/stable/
        StreetFighterIISpecialChampionEdition-Genesis-v0/rom.md
    Expected SHA1: a5aad1d108046d9388e33247610dafb4c6516e0b

No Docker, FastAPI, Celery, or any other service required.
"""

import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"  # No display in WSL2

import numpy as np
import stable_retro

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"
NUM_FRAMES = 300  # ~5 seconds at 60fps
SAVE_FRAMES = [1, 60, 120, 180, 240, 300]  # Capture snapshots at these frames


def main():
    print("=" * 60)
    print("stable-retro standalone test")
    print("=" * 60)

    # 1. Verify ROM is installed
    print(f"\n[1/5] Checking ROM for {GAME}...")
    try:
        rom_path = stable_retro.data.get_romfile_path(GAME)
        print(f"  ROM found: {rom_path}")
    except FileNotFoundError:
        print("  ERROR: ROM not found. See docstring for setup instructions.")
        sys.exit(1)

    # 2. Create environment
    print(f"\n[2/5] Creating environment (2-player, FILTERED actions)...")
    env = stable_retro.make(
        GAME,
        players=2,
        use_restricted_actions=stable_retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=stable_retro.data.Integrations.ALL,
    )
    print(f"  Action space: {env.action_space}")
    print(f"  Buttons: {env.buttons}")

    # 3. Reset and verify initial state
    print(f"\n[3/5] Resetting environment...")
    obs, info = env.reset()
    print(f"  Obs shape: {obs.shape}")
    print(f"  Initial info: {info}")

    # 4. Run frames with random actions
    print(f"\n[4/5] Running {NUM_FRAMES} frames with random actions...")
    start = time.time()
    frames_saved = []

    for frame in range(1, NUM_FRAMES + 1):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)

        if frame in SAVE_FRAMES:
            try:
                from PIL import Image

                filename = f"sf2_frame_{frame:04d}.png"
                filepath = os.path.join("/mnt/c/Projects/Rawl", filename)
                Image.fromarray(obs).save(filepath)
                frames_saved.append(filename)
            except ImportError:
                pass  # Pillow not installed, skip frame saving

        if terminated or truncated:
            print(f"  Episode ended at frame {frame} (terminated={terminated}, truncated={truncated})")
            obs, info = env.reset()

    elapsed = time.time() - start
    fps = NUM_FRAMES / elapsed
    print(f"  Done: {NUM_FRAMES} frames in {elapsed:.2f}s ({fps:.1f} FPS)")

    # 5. Final state
    print(f"\n[5/5] Final game state:")
    print(f"  P1 health:      {info.get('health', 'N/A')}")
    print(f"  P2 health:      {info.get('enemy_health', 'N/A')}")
    print(f"  P1 matches won: {info.get('matches_won', 'N/A')}")
    print(f"  P2 matches won: {info.get('enemy_matches_won', 'N/A')}")
    print(f"  Timer:          {info.get('continuetimer', 'N/A')}")
    print(f"  Score:          {info.get('score', 'N/A')}")

    if frames_saved:
        print(f"\n  Saved frames: {', '.join(frames_saved)}")
        print(f"  Location: C:\\Projects\\Rawl\\")

    env.close()

    print("\n" + "=" * 60)
    print("PASSED — stable-retro is working correctly")
    print("=" * 60)


if __name__ == "__main__":
    main()
