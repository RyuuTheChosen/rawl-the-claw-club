#!/usr/bin/env python3
"""End-to-end integration test for the calibration pipeline.

Runs real SF2 calibration matches via stable-retro against reference models
stored in MinIO. Verifies the full flow:
  1. Create test user + fighter in PostgreSQL
  2. Upload fighter model to MinIO
  3. Run run_calibration() with real emulation
  4. Verify: CalibrationMatch records, Elo updated, stats updated, status ready

This script must run in WSL2 where stable-retro is available.
It connects to Docker services on the Windows host (10.255.255.254).

Usage:
    wsl -d Ubuntu-22.04 -- bash -lc "SDL_VIDEODRIVER=dummy python3 /mnt/c/Projects/Rawl/scripts/test_calibration_e2e.py"

Prerequisites:
    - Docker services running (PostgreSQL, Redis, MinIO)
    - Reference models uploaded (python scripts/upload_reference_models.py)
    - WSL2 with stable-retro + stable_baselines3
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

# Override env vars to point to Windows host Docker services BEFORE any imports
HOST = os.environ.get("DOCKER_HOST_IP", "10.255.255.254")
os.environ.setdefault("DATABASE_URL", f"postgresql+asyncpg://rawl:rawl@{HOST}:5432/rawl")
os.environ.setdefault("REDIS_URL", f"redis://{HOST}:6379/0")
os.environ.setdefault("S3_ENDPOINT", f"http://{HOST}:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("S3_BUCKET", "rawl-replays")
os.environ.setdefault("S3_REGION", "us-east-1")
os.environ.setdefault("SOLANA_RPC_URL", f"http://{HOST}:8899")
os.environ.setdefault("PROGRAM_ID", "AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K")
os.environ.setdefault("ORACLE_KEYPAIR_PATH", "/mnt/c/Projects/Rawl/oracle-keypair.json")

# Polyfill datetime.UTC for Python 3.10 (added in 3.11)
import datetime
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc

# Add backend to path
sys.path.insert(0, "/mnt/c/Projects/Rawl/packages/backend/src")

DIVIDER = "=" * 64
SEP = "-" * 64
MODEL_PATH = "/mnt/c/Projects/Rawl/models/sf2_baseline.zip"
FIGHTER_S3_KEY = "test-calibration/test_fighter_model.zip"


async def main():
    from sqlalchemy import select, func as sqla_func

    from rawl.db.session import async_session_factory
    from rawl.db.models.user import User
    from rawl.db.models.fighter import Fighter
    from rawl.db.models.calibration_match import CalibrationMatch
    from rawl.s3_client import upload_bytes
    from rawl.services.elo import run_calibration

    print(DIVIDER)
    print("  CALIBRATION E2E INTEGRATION TEST")
    print(DIVIDER)
    print(f"  DB host:  {HOST}:5432")
    print(f"  S3 host:  {HOST}:9000")
    print(f"  Model:    {MODEL_PATH}")
    print()

    # Step 1: Upload fighter model to MinIO
    print(f"{SEP}")
    print("  Step 1: Upload test fighter model to MinIO")
    print(f"{SEP}")
    with open(MODEL_PATH, "rb") as f:
        model_bytes = f.read()
    ok = await upload_bytes(FIGHTER_S3_KEY, model_bytes)
    print(f"  Upload {FIGHTER_S3_KEY}: {'OK' if ok else 'FAILED'}")
    if not ok:
        print("  [ERROR] Cannot continue without model in S3")
        return False

    # Step 2: Create test user + fighter in DB
    print(f"\n{SEP}")
    print("  Step 2: Create test fighter in DB (status=calibrating)")
    print(f"{SEP}")

    fighter_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with async_session_factory() as db:
        user = User(
            id=user_id,
            wallet_address=f"TestCal{str(user_id)[:30]}",
        )
        db.add(user)
        await db.flush()

        fighter = Fighter(
            id=fighter_id,
            owner_id=user_id,
            name="CalibrationTestBot",
            game_id="sf2ce",
            character="Ryu",
            model_path=FIGHTER_S3_KEY,
            elo_rating=1200.0,
            matches_played=0,
            wins=0,
            losses=0,
            status="calibrating",
            division_tier="Silver",
        )
        db.add(fighter)
        await db.commit()

    print(f"  Fighter ID: {fighter_id}")
    print(f"  Status:     calibrating")
    print(f"  Elo:        1200.0")
    print(f"  Matches:    0")

    # Step 3: Run calibration
    print(f"\n{SEP}")
    print("  Step 3: Run calibration (5 reference matches)")
    print(f"{SEP}")
    print("  This will run 5 real SF2 matches via stable-retro...")
    print()

    async with async_session_factory() as db:
        success = await run_calibration(str(fighter_id), db)

    print(f"\n  run_calibration() returned: {success}")

    # Step 4: Verify results
    print(f"\n{SEP}")
    print("  Step 4: Verify results")
    print(f"{SEP}")

    results = {}

    async with async_session_factory() as db:
        # Reload fighter
        result = await db.execute(select(Fighter).where(Fighter.id == fighter_id))
        fighter = result.scalar_one()

        print(f"\n  Fighter state after calibration:")
        print(f"    Status:         {fighter.status}")
        print(f"    Elo:            {fighter.elo_rating}")
        print(f"    Division:       {fighter.division_tier}")
        print(f"    Matches played: {fighter.matches_played}")
        print(f"    Wins:           {fighter.wins}")
        print(f"    Losses:         {fighter.losses}")

        # Check CalibrationMatch records
        cal_result = await db.execute(
            select(CalibrationMatch)
            .where(CalibrationMatch.fighter_id == fighter_id)
            .order_by(CalibrationMatch.created_at)
        )
        cal_matches = cal_result.scalars().all()

        print(f"\n  CalibrationMatch records: {len(cal_matches)}")
        wins = 0
        losses = 0
        errors = 0
        for cm in cal_matches:
            status_icon = {"win": "+", "loss": "-", "error": "!"}
            icon = status_icon.get(cm.result, "?")
            elo_str = f"  Elo change: {cm.elo_change:+.1f}" if cm.elo_change else ""
            err_str = f"  Error: {cm.error_message[:60]}" if cm.error_message else ""
            print(f"    [{icon}] ref_elo={cm.reference_elo}  result={cm.result}"
                  f"  attempt={cm.attempt}{elo_str}{err_str}")
            if cm.result == "win":
                wins += 1
            elif cm.result == "loss":
                losses += 1
            elif cm.result == "error":
                errors += 1

        successes = wins + losses  # completed matches (not errors)
        print(f"\n  Completed: {successes} (wins={wins}, losses={losses}, errors={errors})")

        # Assertions
        results["has_cal_records"] = len(cal_matches) >= 5
        results["enough_successes"] = successes >= 3
        results["status_correct"] = fighter.status == ("ready" if successes >= 3 else "calibration_failed")
        results["elo_changed"] = fighter.elo_rating != 1200.0
        results["matches_played_updated"] = fighter.matches_played == successes
        results["wins_match"] = fighter.wins == wins
        results["losses_match"] = fighter.losses == (successes - wins)
        results["division_set"] = fighter.division_tier in ("Bronze", "Silver", "Gold", "Diamond")

        # K-factor check: with successes calibration matches played,
        # the fighter should still be in calibration K-factor range (< 10 matches)
        if successes <= 5:
            results["k_factor_range"] = fighter.matches_played < 10
        else:
            results["k_factor_range"] = True

    # Print results
    print(f"\n{SEP}")
    print("  VERIFICATION")
    print(f"{SEP}")
    all_pass = True
    for check, passed in results.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {check}")
        if not passed:
            all_pass = False

    print(f"\n{DIVIDER}")
    print(f"  RESULT: {'ALL PASS' if all_pass else 'FAIL'}")
    print(f"  Fighter: {fighter_id}")
    print(DIVIDER)

    # Cleanup: delete test data
    async with async_session_factory() as db:
        await db.execute(
            CalibrationMatch.__table__.delete().where(
                CalibrationMatch.fighter_id == fighter_id
            )
        )
        await db.execute(
            Fighter.__table__.delete().where(Fighter.id == fighter_id)
        )
        await db.execute(
            User.__table__.delete().where(User.id == user_id)
        )
        await db.commit()
    print("\n  Test data cleaned up.")

    return all_pass


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
