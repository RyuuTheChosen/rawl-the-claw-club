"""Upload pretrained models to MinIO as reference fighters for calibration.

Uses the baseline model at all 5 Elo levels. The calibration Elo calculation
uses the tagged reference Elo (not actual model skill), so identical models
are valid for testing. Production should use differently-skilled reference bots.

Usage:
    cd packages/backend && python ../../scripts/upload_reference_models.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend src to path for rawl imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "backend" / "src"))

from rawl.s3_client import upload_bytes

REFERENCE_ELOS = [1000, 1100, 1200, 1400, 1600]
GAME_ID = "sf2ce"
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "sf2_baseline.zip"


async def main():
    if not MODEL_PATH.exists():
        print(f"ERROR: Model not found at {MODEL_PATH}")
        sys.exit(1)

    model_bytes = MODEL_PATH.read_bytes()
    size_mb = len(model_bytes) / (1024 * 1024)
    print(f"Loaded {MODEL_PATH.name} ({size_mb:.1f} MB)")

    for elo in REFERENCE_ELOS:
        key = f"reference/{GAME_ID}/{elo}"
        ok = await upload_bytes(key, model_bytes)
        status = "OK" if ok else "FAILED"
        print(f"  {key} ... {status}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
