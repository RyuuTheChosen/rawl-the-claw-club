#!/usr/bin/env python3
"""Generate save states for SF2CE with different character matchups.

Creates .state files for stable-retro so the emulation engine can play
different character matchups instead of the same default every time.

Approach: Advance through 1P mode (making P1 invincible), save each fight
state, then patch the mode byte (0x81D9=0) + combat byte (0x812A=3) to
convert from 1P (CPU opponent) to 2P (human controls both players).

Also generates a natural 2P Sagat state by booting to VS Battle mode.

Usage (run in WSL2):
    # List available built-in + custom states
    python3 scripts/generate_sf2ce_states.py --list

    # Generate all opponent states (Ryu vs each character)
    python3 scripts/generate_sf2ce_states.py --auto

    # Include debug PNGs of each state
    python3 scripts/generate_sf2ce_states.py --auto --debug-frames
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"

# Add backend src to path for character registry
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "packages" / "backend" / "src"
sys.path.insert(0, str(_BACKEND_SRC))

import numpy as np

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"

# Genesis controller: 12 buttons per player
B, A, MODE, START, UP, DOWN, LEFT, RIGHT, C, Y, X, Z = range(12)

# Character IDs in ROM order
CHAR_NAMES = {
    0: "Ryu", 1: "Honda", 2: "Blanka", 3: "Guile", 4: "Ken", 5: "ChunLi",
    6: "Zangief", 7: "Dhalsim", 8: "Balrog", 9: "Sagat", 10: "Vega", 11: "Bison",
}

# RAM addresses (offsets from start of 68000 RAM)
RAM_BASE = 16          # Offset of RAM in state blob
P1_CHAR = 0x81DA       # P1 character ID
P2_CHAR = 0x845A       # P2 character ID
P1_HEALTH = 0x8042     # P1 health (max 176)
P2_HEALTH = 0x82C2     # P2 health (max 176)
MODE_BYTE = 0x81D9     # 1=CPU opponent, 0=human (P1+0x1D9)
COMBAT_P1 = 0x812A     # 0=disabled, 3=active (P1+0x12A)

OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "packages" / "backend" / "src" / "rawl"
    / "engine" / "emulation" / "states" / "sf2ce"
)


def _make_action(p1=None, p2=None):
    """Build a 24-element MultiBinary action array."""
    a = np.zeros(24, dtype=np.int8)
    for btn in p1 or []:
        a[btn] = 1
    for btn in p2 or []:
        a[12 + btn] = 1
    return a


NOOP = _make_action()


def _step_n(env, n, p1=None, p2=None):
    """Step the environment N frames with given buttons held."""
    a = _make_action(p1, p2)
    obs = info = None
    for _ in range(n):
        obs, _, _, _, info = env.step(a)
    return obs, info


def _save_debug_frame(obs, path):
    """Save an observation as a PNG for debugging."""
    try:
        from PIL import Image
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(obs).save(path)
    except ImportError:
        pass


def _make_env(use_default=False):
    """Create a stable-retro environment."""
    import stable_retro as retro
    kw = dict(
        players=2,
        use_restricted_actions=retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=retro.data.Integrations.ALL,
    )
    if not use_default:
        kw["state"] = retro.State.NONE
    return retro.make(GAME, **kw)


def _patch_to_2p(state_bytes):
    """Convert a 1P fight state to 2P by patching mode + combat bytes."""
    p = bytearray(state_bytes)
    p[RAM_BASE + MODE_BYTE] = 0     # CPU → human
    p[RAM_BASE + COMBAT_P1] = 3     # enable P1 combat
    return bytes(p)


def _is_2p_mode(state_bytes, frames=300):
    """Verify state is 2P: P1 health should be unchanged after idle frames."""
    env = _make_env(use_default=True)
    env.reset()
    env.unwrapped.em.set_state(state_bytes)
    ram = env.unwrapped.get_ram()
    h0 = ram[P1_HEALTH]
    for _ in range(frames):
        env.step(NOOP)
    ram = env.unwrapped.get_ram()
    h1 = ram[P1_HEALTH]
    env.close()
    return h0 == h1


def _combat_test(state_bytes):
    """Quick combat test: walk toward each other + attack. Returns (p1_dmg, p2_dmg)."""
    env = _make_env(use_default=True)
    env.reset()
    env.unwrapped.em.set_state(state_bytes)
    ram = env.unwrapped.get_ram()
    h0_p1, h0_p2 = ram[P1_HEALTH], ram[P2_HEALTH]

    # Walk toward each other
    _step_n(env, 120, p1=[RIGHT], p2=[LEFT])

    # Multiple attack types
    for _ in range(10):
        _step_n(env, 2, p1=[Y])      # medium punch
        _step_n(env, 6)
        _step_n(env, 2, p1=[B])      # low kick
        _step_n(env, 6)
        _step_n(env, 2, p1=[A])      # heavy punch
        _step_n(env, 6)
        _step_n(env, 2, p1=[C])      # heavy kick
        _step_n(env, 6)

    # P2 attacks
    for _ in range(10):
        _step_n(env, 2, p2=[Y])
        _step_n(env, 6)
        _step_n(env, 2, p2=[B])
        _step_n(env, 6)

    ram = env.unwrapped.get_ram()
    h1_p1, h1_p2 = ram[P1_HEALTH], ram[P2_HEALTH]
    env.close()
    return h0_p1 - h1_p1, h0_p2 - h1_p2


def generate_1p_opponents(debug=False):
    """Advance through 1P mode, saving each fight state before winning.

    Makes P1 invincible (health=176 every 30 frames) and attacks aggressively
    to beat each opponent. After defeating one, the game loads the next.

    Returns list of (char_id, char_name, state_bytes) tuples.
    """
    print("=== Advancing through 1P mode ===")
    debug_dir = OUTPUT_DIR / "debug" / "opponents" if debug else None

    env = _make_env(use_default=True)
    env.reset()
    # Let initial state settle
    for _ in range(120):
        env.step(NOOP)

    opponents = []
    seen = set()

    for idx in range(12):
        ram = env.unwrapped.get_ram()
        p2c = ram[P2_CHAR]
        p2name = CHAR_NAMES.get(p2c, f"unk{p2c}")

        if p2c in seen:
            print(f"\n  Repeat {p2name} — stopping")
            break

        p1h, p2h = ram[P1_HEALTH], ram[P2_HEALTH]
        print(f"\n  Opponent {idx + 1}: Ryu vs {p2name} (health={p1h}/{p2h})")

        fight_state = env.unwrapped.em.get_state()
        opponents.append((p2c, p2name, fight_state))
        seen.add(p2c)

        if debug_dir:
            obs, _ = _step_n(env, 1)
            _save_debug_frame(obs, debug_dir / f"opp{idx + 1}_{p2name}.png")

        # Win the match: P1 invincible + aggressive attacks
        for frame in range(30000):
            # Keep P1 health maxed
            if frame % 30 == 0:
                s = env.unwrapped.em.get_state()
                p = bytearray(s)
                p[RAM_BASE + P1_HEALTH] = 176
                env.unwrapped.em.set_state(bytes(p))

            # Aggressive attack pattern
            phase = frame % 20
            if phase < 4:
                env.step(_make_action(p1=[RIGHT]))
            elif phase < 6:
                env.step(_make_action(p1=[Y]))      # medium punch
            elif phase < 8:
                env.step(_make_action(p1=[C]))       # heavy kick
            elif phase < 10:
                env.step(_make_action(p1=[A]))       # heavy punch
            elif phase < 12:
                env.step(_make_action(p1=[RIGHT, DOWN]))
            elif phase < 14:
                env.step(_make_action(p1=[B]))       # low kick
            else:
                env.step(NOOP)

            ram = env.unwrapped.get_ram()
            if ram[P2_CHAR] != p2c and ram[P2_HEALTH] > 0:
                new_name = CHAR_NAMES.get(ram[P2_CHAR], "?")
                print(f"    Advanced at {frame}f → {new_name}")
                # Long settle time for proper state initialization
                for _ in range(300):
                    env.step(NOOP)
                break
        else:
            print(f"    Stuck after 30000f — trying START skip")
            for _ in range(3):
                _step_n(env, 3, p1=[START])
                _step_n(env, 180)
            ram = env.unwrapped.get_ram()
            if ram[P2_CHAR] != p2c and ram[P2_HEALTH] > 0:
                new_name = CHAR_NAMES.get(ram[P2_CHAR], "?")
                print(f"    Advanced after START → {new_name}")
                for _ in range(300):
                    env.step(NOOP)
            else:
                print(f"    Cannot advance past {p2name}")
                break

    env.close()
    print(f"\n  Collected {len(opponents)} opponents from 1P mode")
    return opponents


def generate_2p_sagat():
    """Generate a natural 2P Sagat state by booting to VS Battle mode."""
    print("\n=== Generating natural 2P Sagat ===")
    env = _make_env()
    env.reset()

    # Boot sequence: title → VS Battle → fight
    _step_n(env, 2050)                      # Boot ROM to title
    _step_n(env, 3, p1=[START])             # Title → mode select
    _step_n(env, 30, p1=[DOWN])             # Navigate to VS Battle
    _step_n(env, 10)                        # Release
    _step_n(env, 3, p1=[START])             # Confirm VS Battle

    # Wait for fight to start
    for _ in range(600):
        obs, _, _, _, info = env.step(NOOP)
        if info.get("health", 0) > 0:
            break
    for _ in range(30):
        env.step(NOOP)

    state = env.unwrapped.em.get_state()
    ram = env.unwrapped.get_ram()
    p1_name = CHAR_NAMES.get(ram[P1_CHAR], "?")
    p2_name = CHAR_NAMES.get(ram[P2_CHAR], "?")
    print(f"  {p1_name} vs {p2_name} (natural 2P)")
    env.close()
    return state


def list_states():
    """Print all built-in and custom states for the game."""
    import stable_retro as retro

    try:
        states = retro.data.list_states(GAME, inttype=retro.data.Integrations.ALL)
        print(f"Built-in states for {GAME}:")
        for s in sorted(states):
            print(f"  - {s}")
        if not states:
            print("  (none)")
    except Exception as e:
        print(f"Error listing states: {e}")

    if OUTPUT_DIR.is_dir():
        custom = sorted(OUTPUT_DIR.glob("*.state"))
        if custom:
            print(f"\nCustom states in {OUTPUT_DIR}:")
            for p in custom:
                print(f"  - {p.stem} ({p.stat().st_size} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Generate SF2CE save states for match variety")
    parser.add_argument("--list", action="store_true", help="List available states")
    parser.add_argument("--auto", action="store_true", help="Generate all opponent states")
    parser.add_argument("--debug-frames", action="store_true", help="Save debug PNGs")
    args = parser.parse_args()

    if args.list:
        list_states()
        return

    if not args.auto:
        parser.print_help()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Advance through 1P mode to collect opponent fight states
    opponents = generate_1p_opponents(debug=args.debug_frames)

    # Step 2: Generate natural 2P Sagat (always Ryu vs Sagat from VS Battle boot)
    sagat_state = generate_2p_sagat()

    # Step 3: Convert 1P states to 2P, verify, and save
    print("\n=== Converting and verifying states ===")

    results = []

    for p2c, p2name, state_bytes in opponents:
        patched = _patch_to_2p(state_bytes)
        is_2p = _is_2p_mode(patched)
        p1d, p2d = _combat_test(patched)
        combat_ok = p1d > 0 or p2d > 0
        results.append((p2name, patched, is_2p, combat_ok, p1d, p2d))

        tag = "2P" if is_2p else "1P!"
        combat_tag = "OK" if combat_ok else "untested"
        print(f"  Ryu vs {p2name:8s}: {tag} combat={combat_tag} P1-{p1d} P2-{p2d}")

    # Add natural Sagat if not already collected as a 1P opponent
    has_sagat = any(name == "Sagat" for name, *_ in results)
    if not has_sagat:
        is_2p = _is_2p_mode(sagat_state)
        p1d, p2d = _combat_test(sagat_state)
        combat_ok = p1d > 0 or p2d > 0
        results.append(("Sagat", sagat_state, is_2p, combat_ok, p1d, p2d))
        tag = "2P" if is_2p else "1P!"
        combat_tag = "OK" if combat_ok else "untested"
        print(f"  Ryu vs Sagat(nat): {tag} combat={combat_tag} P1-{p1d} P2-{p2d}")

    # Step 4: Save all verified 2P states
    print("\n=== Saving states ===")
    saved = 0
    for name, state, is_2p, combat_ok, p1d, p2d in results:
        if not is_2p:
            print(f"  SKIP {name} (failed 2P verification)")
            continue

        out = OUTPUT_DIR / f"Ryu_vs_{name}.state"
        out.write_bytes(state)
        flag = "OK" if combat_ok else "combat-untested"
        print(f"  SAVED: {out.name} [{flag}]")
        saved += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Generated: {saved} states saved to {OUTPUT_DIR}")
    skipped = sum(1 for _, _, is_2p, *_ in results if not is_2p)
    if skipped:
        print(f"Skipped:   {skipped} (failed 2P verification)")

    if saved:
        print("\nState files:")
        for f in sorted(OUTPUT_DIR.glob("*.state")):
            print(f"  {f.name} ({f.stat().st_size} bytes)")
        print("\nRetroEngine will load them automatically based on fighter characters.")


if __name__ == "__main__":
    main()
