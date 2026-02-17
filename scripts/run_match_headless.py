#!/usr/bin/env python3
"""Run a real SF2 match headless and output the result as JSON.

This script runs inside WSL2 where stable-retro is available.
It uses random actions (no models needed) and tracks rounds using
the same delta-tracking logic as the SF2CE game adapter.

Usage (from WSL2):
    SDL_VIDEODRIVER=dummy python3 scripts/run_match_headless.py --format 3

Output: JSON on stdout with winner, round_history, frame_count
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import stable_retro

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"
MAX_HEALTH = 176
MAX_FRAMES = 60 * 60 * 5  # 5 minutes at 60fps safety cap


def run_match(match_format: int = 3) -> dict:
    env = stable_retro.make(
        GAME,
        players=2,
        use_restricted_actions=stable_retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=stable_retro.data.Integrations.ALL,
    )
    obs, info = env.reset()

    wins_needed = (match_format // 2) + 1
    prev_p1_wins = 0
    prev_p2_wins = 0
    round_history = []
    frame_count = 0

    while frame_count < MAX_FRAMES:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        frame_count += 1

        p1_wins = info.get("matches_won", 0)
        p2_wins = info.get("enemy_matches_won", 0)

        # Delta-based round detection (same as SF2CEAdapter)
        round_winner = None
        if p1_wins > prev_p1_wins:
            round_winner = "P1"
            prev_p1_wins = p1_wins
        elif p2_wins > prev_p2_wins:
            round_winner = "P2"
            prev_p2_wins = p2_wins

        if round_winner:
            p1_hp = max(0.0, info.get("health", 0) / MAX_HEALTH)
            p2_hp = max(0.0, info.get("enemy_health", 0) / MAX_HEALTH)
            round_history.append({
                "winner": round_winner,
                "p1_health": round(p1_hp, 4),
                "p2_health": round(p2_hp, 4),
            })
            print(
                f"  Round {len(round_history)}: {round_winner} wins "
                f"(P1 HP: {p1_hp:.0%}, P2 HP: {p2_hp:.0%}) @ frame {frame_count}",
                file=sys.stderr,
            )

            # Check match over
            total_p1 = sum(1 for r in round_history if r["winner"] == "P1")
            total_p2 = sum(1 for r in round_history if r["winner"] == "P2")
            if total_p1 >= wins_needed:
                env.close()
                return {
                    "winner": "P1",
                    "round_history": round_history,
                    "frame_count": frame_count,
                }
            if total_p2 >= wins_needed:
                env.close()
                return {
                    "winner": "P2",
                    "round_history": round_history,
                    "frame_count": frame_count,
                }

        if terminated or truncated:
            # Episode ended before match complete — reset and continue
            obs, info = env.reset()
            prev_p1_wins = 0
            prev_p2_wins = 0

    env.close()
    return {
        "winner": None,
        "round_history": round_history,
        "frame_count": frame_count,
        "error": "max_frames_exceeded",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", type=int, default=3, help="Match format (Bo3=3, Bo5=5)")
    args = parser.parse_args()

    print(f"Running SF2 match (Bo{args.format}) with random actions...", file=sys.stderr)
    result = run_match(args.format)
    print(f"Result: {result['winner']} in {result['frame_count']} frames", file=sys.stderr)

    # Output clean JSON to stdout (parsed by the settlement script)
    print(json.dumps(result))
