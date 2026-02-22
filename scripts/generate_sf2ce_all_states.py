#!/usr/bin/env python3
"""Generate all 144 SF2CE matchup states (12×12 character combinations).

VS Battle mode eliminates all per-character AI complexity — no timer fixes,
no mercy mechanic handling needed. Both players are human-controlled
(MODE_BYTE=0 naturally), so the idle test trivially passes for every pair.

Proven approach: `ryu_vs_sagat.state` was generated the same way and passes.

Run in WSL2:
    # Dry run (4 sample pairs — ~10 min)
    wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/c/Projects/Rawl && python3 scripts/generate_sf2ce_all_states.py --dry-run --debug"

    # Full run, skip existing, skip combat for speed (~4 h)
    wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/c/Projects/Rawl && python3 scripts/generate_sf2ce_all_states.py --skip-combat 2>&1 | tee /tmp/sf2ce_gen.log"

    # Regenerate all including existing (fixes Ken P1H=151→176, etc.)
    wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/c/Projects/Rawl && python3 scripts/generate_sf2ce_all_states.py --force --skip-combat"
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"

import numpy as np

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"

STATE_DIR = Path(
    "/mnt/c/Projects/Rawl/packages/backend/src/rawl/engine/emulation/states/sf2ce"
)
DEBUG_DIR = STATE_DIR / "debug" / "all_states_gen"

# Genesis controller buttons (12 per player)
B, A, MODE, START, UP, DOWN, LEFT, RIGHT, C, Y, X, Z = range(12)

# Character IDs in ROM order
CHAR_NAMES = {
    0: "Ryu", 1: "Honda", 2: "Blanka", 3: "Guile", 4: "Ken", 5: "ChunLi",
    6: "Zangief", 7: "Dhalsim", 8: "Balrog", 9: "Sagat", 10: "Vega", 11: "Bison",
}

# RAM addresses (offsets into the state blob's 68000 RAM region)
RAM_BASE   = 16
P1_CHAR    = 0x81DA
P2_CHAR    = 0x845A
P1_HEALTH  = 0x8042
P2_HEALTH  = 0x82C2
MODE_BYTE  = 0x81D9    # 1=CPU opponent, 0=human (already 0 in VS Battle)
COMBAT_P1  = 0x812A    # 0=disabled, 3=active
COMBAT_P2  = 0x83AA    # 0=disabled, 3=active
MAX_HEALTH = 176


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def act(p1=None, p2=None):
    """Build a 24-element MultiBinary action array."""
    a = np.zeros(24, dtype=np.int8)
    for b in p1 or []:
        a[b] = 1
    for b in p2 or []:
        a[12 + b] = 1
    return a


NOOP = act()


def step_n(env, n, p1=None, p2=None):
    """Step N frames; return (obs, info) from the last step."""
    a = act(p1, p2)
    obs = info = None
    for _ in range(n):
        obs, _, _, _, info = env.step(a)
    return obs, info


def make_env_none():
    """Create an env that boots from ROM (no saved state)."""
    import stable_retro as retro
    return retro.make(
        GAME,
        state=retro.State.NONE,
        players=2,
        use_restricted_actions=retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=retro.data.Integrations.ALL,
    )


def make_env_default():
    """Create an env with the built-in default state (used for tests)."""
    import stable_retro as retro
    return retro.make(
        GAME,
        players=2,
        use_restricted_actions=retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=retro.data.Integrations.ALL,
    )


def save_img(obs, name):
    """Save an observation frame as PNG to DEBUG_DIR."""
    from PIL import Image
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray(obs).save(DEBUG_DIR / f"{name}.png")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def idle_test(state_bytes, frames=300):
    """Load state and step NOOP for N frames.

    Returns (passed, h0, h1, first_hit_frame).
    In VS Battle mode both players are human-controlled so neither takes
    damage automatically — this should always pass.
    """
    env = make_env_default()
    try:
        env.reset()
        env.unwrapped.em.set_state(state_bytes)
        ram = env.unwrapped.get_ram()
        h0 = ram[P1_HEALTH]
        last_h = h0
        first_hit = -1
        for f in range(frames):
            env.step(NOOP)
            ram = env.unwrapped.get_ram()
            h = ram[P1_HEALTH]
            if h < last_h and first_hit == -1:
                first_hit = f
                last_h = h
        return last_h == h0, h0, last_h, first_hit
    finally:
        env.close()


def combat_test(state_bytes):
    """Walk toward each other and attack. Returns (p1_dmg, p2_dmg)."""
    env = make_env_default()
    try:
        env.reset()
        env.unwrapped.em.set_state(state_bytes)
        ram = env.unwrapped.get_ram()
        h0_p1, h0_p2 = ram[P1_HEALTH], ram[P2_HEALTH]

        # Close the gap
        step_n(env, 120, p1=[RIGHT], p2=[LEFT])

        # P1 attacks P2
        for _ in range(15):
            step_n(env, 2, p1=[Y])    # medium punch
            step_n(env, 6)
            step_n(env, 2, p1=[C])    # heavy kick
            step_n(env, 6)

        # P2 attacks P1
        for _ in range(10):
            step_n(env, 2, p2=[Y])
            step_n(env, 6)

        ram = env.unwrapped.get_ram()
        return h0_p1 - ram[P1_HEALTH], h0_p2 - ram[P2_HEALTH]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# Idle-warn fix
# ---------------------------------------------------------------------------

def fix_idle_warn(state_bytes, p1_id, p2_id, settle_frames=300):
    """Advance an existing state N frames with P1 invincible to push past
    any residual CPU attack windows, then re-apply safety patches.

    Much faster than regenerating from scratch (no ROM boot needed).
    Returns fixed state_bytes.
    """
    env = make_env_default()
    try:
        env.reset()
        env.unwrapped.em.set_state(state_bytes)
        for f in range(settle_frames):
            env.step(NOOP)
            if f % 30 == 0:
                s = env.unwrapped.em.get_state()
                blob = bytearray(s)
                blob[RAM_BASE + P1_HEALTH] = MAX_HEALTH  # keep P1 alive
                blob[RAM_BASE + P1_CHAR]   = p1_id       # lock chars
                blob[RAM_BASE + P2_CHAR]   = p2_id
                env.unwrapped.em.set_state(bytes(blob))
        state = env.unwrapped.em.get_state()
        blob = bytearray(state)
        blob[RAM_BASE + MODE_BYTE]  = 0
        blob[RAM_BASE + COMBAT_P1]  = 3
        blob[RAM_BASE + COMBAT_P2]  = 3
        blob[RAM_BASE + P1_CHAR]    = p1_id
        blob[RAM_BASE + P2_CHAR]    = p2_id
        blob[RAM_BASE + P1_HEALTH]  = MAX_HEALTH
        blob[RAM_BASE + P2_HEALTH]  = MAX_HEALTH
        return bytes(blob)
    finally:
        env.close()


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def generate_pair_state(p1_id, p2_id, debug=False):
    """Generate a VS Battle fight state for (p1_id, p2_id).

    Boot sequence (VS Battle — same as generate_2p_sagat in generate_sf2ce_states.py):
        title (2050f) → mode select (START) → navigate to VS Battle (DOWN×30)
        → release (10f) → confirm (START)

    Then wait up to 600 frames for fight to start, patching P1_CHAR + P2_CHAR
    every frame so the correct sprites load. Once P1_HEALTH > 100 (fight active),
    apply safety patches and return (state_bytes, obs).

    Returns (None, None) on timeout.
    """
    p1_name = CHAR_NAMES[p1_id]
    p2_name = CHAR_NAMES[p2_id]

    env = make_env_none()
    try:
        env.reset()

        # VS Battle boot sequence
        step_n(env, 2050)                   # boot ROM to title screen
        step_n(env, 3,  p1=[START])         # title → mode select
        step_n(env, 30, p1=[DOWN])          # navigate down to VS Battle
        step_n(env, 10)                     # release
        step_n(env, 3,  p1=[START])         # confirm VS Battle

        # Wait up to 600 frames for fight to start, patching chars every frame
        fight_started = False
        obs_at_start = None
        for _ in range(600):
            obs, _ = step_n(env, 1)
            s = env.unwrapped.em.get_state()
            blob = bytearray(s)
            blob[RAM_BASE + P1_CHAR] = p1_id
            blob[RAM_BASE + P2_CHAR] = p2_id
            env.unwrapped.em.set_state(bytes(blob))
            if env.unwrapped.get_ram()[P1_HEALTH] > 100:
                obs_at_start = obs
                fight_started = True
                break

        if not fight_started:
            print(f"    TIMEOUT — fight never started for {p1_name} vs {p2_name}")
            return None, None

        # Capture state and apply safety patches
        state = env.unwrapped.em.get_state()
        blob = bytearray(state)
        blob[RAM_BASE + MODE_BYTE]  = 0           # human (already 0 in VS Battle)
        blob[RAM_BASE + COMBAT_P1]  = 3           # enable P1 combat
        blob[RAM_BASE + COMBAT_P2]  = 3           # enable P2 combat
        blob[RAM_BASE + P1_CHAR]    = p1_id       # lock character IDs
        blob[RAM_BASE + P2_CHAR]    = p2_id
        blob[RAM_BASE + P1_HEALTH]  = MAX_HEALTH  # full health at fight start
        blob[RAM_BASE + P2_HEALTH]  = MAX_HEALTH

        state_bytes = bytes(blob)

        if debug and obs_at_start is not None:
            save_img(obs_at_start, f"{p1_name.lower()}_vs_{p2_name.lower()}_start")

        return state_bytes, obs_at_start

    finally:
        env.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate all 144 SF2CE matchup states (12×12 characters)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate 4 sample pairs and exit (quick ~10 min validation)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate pairs even if state file already exists",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Save a PNG screenshot for each generated state",
    )
    parser.add_argument(
        "--skip-combat", action="store_true",
        help="Skip combat_test (saves ~35%% time on a full run)",
    )
    parser.add_argument(
        "--fix-idle", action="store_true",
        help="Scan all existing states, advance 300 settle frames on failures, re-save",
    )
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # --- Fix idle-warn: load, settle, re-save ---
    if args.fix_idle:
        print("=" * 72)
        print("SF2CE Idle-Warn Fix — settle 300 frames on failing states")
        print("=" * 72)
        n_ok = n_fixed = n_still_fail = n_missing = 0
        for p1_id in range(12):
            for p2_id in range(12):
                p1_name = CHAR_NAMES[p1_id]
                p2_name = CHAR_NAMES[p2_id]
                path = STATE_DIR / f"{p1_name.lower()}_vs_{p2_name.lower()}.state"
                if not path.exists():
                    print(f"  MISSING {p1_name} vs {p2_name}")
                    n_missing += 1
                    continue
                state = path.read_bytes()
                ok, h0, h1, fhit = idle_test(state)
                if ok:
                    print(f"  OK     {p1_name:8s} vs {p2_name}")
                    n_ok += 1
                    continue
                print(f"  FIX    {p1_name:8s} vs {p2_name:8s} (f{fhit}) ...", end="", flush=True)
                fixed = fix_idle_warn(state, p1_id, p2_id, settle_frames=600)
                ok2, h0, h1, fhit2 = idle_test(fixed)
                if ok2:
                    path.write_bytes(fixed)
                    print(" FIXED")
                    n_fixed += 1
                else:
                    print(f" STILL_FAIL(f{fhit2}) — keeping original")
                    n_still_fail += 1
        print(f"\n{'=' * 72}")
        print(f"  Already OK  : {n_ok}")
        print(f"  Fixed       : {n_fixed}")
        print(f"  Still fail  : {n_still_fail}")
        print(f"  Missing     : {n_missing}")
        return

    # --- Dry run: 4 diverse sample pairs ---
    if args.dry_run:
        sample_pairs = [
            (0,  4),   # Ryu   vs Ken
            (1, 11),   # Honda vs Bison
            (10, 5),   # Vega  vs ChunLi
            (4,  4),   # Ken   vs Ken (mirror match)
        ]
        print("=" * 72)
        print("DRY RUN — 4 sample pairs")
        print("=" * 72)
        all_ok = True
        for p1_id, p2_id in sample_pairs:
            p1_name = CHAR_NAMES[p1_id]
            p2_name = CHAR_NAMES[p2_id]
            print(f"\n  {p1_name} vs {p2_name}:")
            state, obs = generate_pair_state(p1_id, p2_id, debug=args.debug)
            if state is None:
                print(f"    FAIL — could not generate state")
                all_ok = False
                continue
            blob = bytearray(state)
            p1c = CHAR_NAMES.get(blob[RAM_BASE + P1_CHAR], "?")
            p2c = CHAR_NAMES.get(blob[RAM_BASE + P2_CHAR], "?")
            p1h = blob[RAM_BASE + P1_HEALTH]
            p2h = blob[RAM_BASE + P2_HEALTH]
            print(f"    State: P1={p1c} P2={p2c} P1H={p1h} P2H={p2h}")
            ok, h0, h1, fhit = idle_test(state)
            idle_str = "PASS" if ok else f"FAIL({h0}→{h1} at f{fhit})"
            print(f"    idle={idle_str}")
            if not ok:
                all_ok = False
            if not args.skip_combat:
                p1d, p2d = combat_test(state)
                combat_ok = p1d > 0 or p2d > 0
                print(f"    combat={'OK' if combat_ok else 'NONE'} (P1-{p1d} P2-{p2d})")
            out = STATE_DIR / f"{p1_name.lower()}_vs_{p2_name.lower()}.state"
            out.write_bytes(state)
            print(f"    Saved → {out.name}")
        print("\n" + "=" * 72)
        print(f"Dry run {'PASSED' if all_ok else 'had issues — check output above'}.")
        return

    # --- Full run: all 144 pairs ---
    print("=" * 72)
    print("SF2CE All-States Generation — 144 matchup combinations (12×12)")
    print("=" * 72)

    results = {}  # (p1_id, p2_id) → "OK" | "SKIP" | "FAIL" | "IDLE_WARN"
    n_generated = 0
    n_skipped   = 0
    n_failed    = 0

    for p1_id in range(12):
        for p2_id in range(12):
            p1_name  = CHAR_NAMES[p1_id]
            p2_name  = CHAR_NAMES[p2_id]
            out_path = STATE_DIR / f"{p1_name.lower()}_vs_{p2_name.lower()}.state"

            if not args.force and out_path.exists():
                print(f"  SKIP  {p1_name:8s} vs {p2_name}")
                results[(p1_id, p2_id)] = "SKIP"
                n_skipped += 1
                continue

            print(f"  GEN   {p1_name:8s} vs {p2_name:8s} ...", end="", flush=True)
            state, obs = generate_pair_state(p1_id, p2_id, debug=args.debug)

            if state is None:
                print(" FAIL (timeout)")
                results[(p1_id, p2_id)] = "FAIL"
                n_failed += 1
                continue

            # Idle test — should always pass in VS Battle (no CPU AI)
            ok, h0, h1, fhit = idle_test(state)
            if not ok:
                # Unexpected — log warning but save state anyway for investigation
                print(f" IDLE_WARN({h0}→{h1} at f{fhit})", end="")
                results[(p1_id, p2_id)] = "IDLE_WARN"
            else:
                results[(p1_id, p2_id)] = "OK"

            # Optional combat test
            if not args.skip_combat:
                p1d, p2d = combat_test(state)
                combat_ok = p1d > 0 or p2d > 0
                combat_str = f" combat={'OK' if combat_ok else 'NONE'}(P1-{p1d} P2-{p2d})"
            else:
                combat_str = ""

            idle_str = "idle=PASS" if ok else "idle=FAIL"
            print(f" {idle_str}{combat_str}")

            out_path.write_bytes(state)
            n_generated += 1

    # --- 12×12 result matrix ---
    # 3-char abbreviated names for compact display
    abbr = {i: CHAR_NAMES[i][:3] for i in range(12)}
    print("\n" + "=" * 72)
    print("Result Matrix  (rows=P1, cols=P2)")
    print("  OK=generated or skipped  WN=idle_warn  FL=failed")
    print()
    header = "     " + " ".join(f"{abbr[i]:>3s}" for i in range(12))
    print(header)
    print("     " + "---+" * 12)
    for p1_id in range(12):
        cells = []
        for p2_id in range(12):
            s = results.get((p1_id, p2_id), "?")
            if s in ("OK", "SKIP"):
                cells.append(" OK")
            elif s == "IDLE_WARN":
                cells.append(" WN")
            elif s == "FAIL":
                cells.append(" FL")
            else:
                cells.append("  ?")
        print(f"  {abbr[p1_id]:>3s} {'|'.join(cells)}")

    # --- Summary ---
    print("\n" + "=" * 72)
    total_ok = n_generated + n_skipped
    n_idle_warn = sum(1 for v in results.values() if v == "IDLE_WARN")
    print(f"  Generated : {n_generated}")
    print(f"  Skipped   : {n_skipped} (already existed)")
    print(f"  Failed    : {n_failed}")
    print(f"  Idle warn : {n_idle_warn} (VS Battle — investigate if > 0)")
    print(f"  Total OK  : {total_ok}/144")

    existing = sorted(STATE_DIR.glob("*.state"))
    print(f"\n  State files on disk: {len(existing)}/144")

    if n_failed > 0:
        print("\n  Failed pairs:")
        for (p1_id, p2_id), status in sorted(results.items()):
            if status == "FAIL":
                print(f"    {CHAR_NAMES[p1_id]} vs {CHAR_NAMES[p2_id]}")

    if n_idle_warn > 0:
        print("\n  Idle-warning pairs (saved but need investigation):")
        for (p1_id, p2_id), status in sorted(results.items()):
            if status == "IDLE_WARN":
                print(f"    {CHAR_NAMES[p1_id]} vs {CHAR_NAMES[p2_id]}")


if __name__ == "__main__":
    main()
