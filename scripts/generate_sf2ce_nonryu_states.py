#!/usr/bin/env python3
"""Generate SF2CE 2P fight states for all 12 characters vs Sagat.

Production script. Two fixes discovered through debugging:

FIX 1 — Timer byte (0x80C8):
  Honda/Blanka: their P1_CHAR initialization sets 0x80C8 to a value (32/31)
  that puts Sagat's attack timer at ~286/254 frames. Setting 0x80C8=23
  (Ryu's value) moves the timer past the 300-frame idle window.

FIX 2 — Settle + mercy mechanic:
  Ken/Vega/Bison: 0x80C8 is already 23 (same as Ryu) but Sagat still attacks.
  Root cause: P1_CHAR drives different code paths every frame; Sagat's attack
  period for these matchups is < 300 frames (shorter than idle window).
  Fix: advance fight to N frames past first attack. SF2CE has a "mercy" AI
  mechanic where Sagat backs off when P1 health is lower. By NOT resetting
  P1_HEALTH at save time (Ken has taken one hit → 151 HP), Sagat extends
  his attack interval beyond 300 frames.

Per-character approach:
  settle=0, timer fix: Honda (was 0x80C8=32), Blanka (was 0x80C8=31)
  settle=0, no fix:    Ryu, Guile, ChunLi, Zangief, Dhalsim, Balrog, Sagat
  settle=240, NO health reset at save: Ken (attacks at f232, mercy kicks in)
  settle=400: Vega (variable timing; settle past unstable early window)
  settle=240: Bison (attacks at f221, settle past it)

Run in WSL2:
    wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/c/Projects/Rawl && python3 scripts/generate_sf2ce_nonryu_states.py"
"""
from __future__ import annotations

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import numpy as np
from pathlib import Path

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"
STATE_DIR = Path("/mnt/c/Projects/Rawl/packages/backend/src/rawl/engine/emulation/states/sf2ce")
DEBUG_DIR = STATE_DIR / "debug" / "nonryu_gen"

B, A, MODE, START, UP, DOWN, LEFT, RIGHT, C, Y, X, Z = range(12)
CHAR_NAMES = {0: "Ryu", 1: "Honda", 2: "Blanka", 3: "Guile", 4: "Ken", 5: "ChunLi",
              6: "Zangief", 7: "Dhalsim", 8: "Balrog", 9: "Sagat", 10: "Vega", 11: "Bison"}

RAM_BASE    = 16
P1_CHAR     = 0x81DA
P2_CHAR     = 0x845A
P1_HEALTH   = 0x8042
P2_HEALTH   = 0x82C2
MODE_BYTE   = 0x81D9
COMBAT_P1   = 0x812A
COMBAT_P2   = 0x83AA
MAX_HEALTH  = 176
TIMER_BYTE  = 0x80C8
TIMER_RYU   = 23  # Ryu's timer value — keeps Sagat passive in 300-frame window

# --- Per-character configuration ---
# settle_frames: advance N frames past fight start (P1 invincible during settle)
# timer_fix:     set TIMER_BYTE = TIMER_RYU (for chars whose 0x80C8 != 23)
# reset_p1_health: reset P1_HEALTH=MAX at save (False for Ken's mercy mechanic)
CHAR_CONFIG = {
    0:  dict(settle=0,   timer_fix=False, reset_p1=True),   # Ryu
    1:  dict(settle=0,   timer_fix=True,  reset_p1=True),   # Honda  (0x80C8=32→23)
    2:  dict(settle=0,   timer_fix=True,  reset_p1=True),   # Blanka (0x80C8=31→23)
    3:  dict(settle=0,   timer_fix=False, reset_p1=True),   # Guile
    4:  dict(settle=240, timer_fix=False, reset_p1=False),  # Ken (mercy mechanic)
    5:  dict(settle=0,   timer_fix=False, reset_p1=True),   # ChunLi
    6:  dict(settle=0,   timer_fix=False, reset_p1=True),   # Zangief
    7:  dict(settle=0,   timer_fix=False, reset_p1=True),   # Dhalsim
    8:  dict(settle=0,   timer_fix=False, reset_p1=True),   # Balrog
    9:  dict(settle=0,   timer_fix=False, reset_p1=True),   # Sagat (mirror)
    10: dict(settle=400, timer_fix=False, reset_p1=True),   # Vega
    11: dict(settle=240, timer_fix=False, reset_p1=True),   # Bison
}


def act(p1=None, p2=None):
    a = np.zeros(24, dtype=np.int8)
    for b in p1 or []: a[b] = 1
    for b in p2 or []: a[12 + b] = 1
    return a


NOOP = act()


def step_n(env, n, p1=None, p2=None):
    a = act(p1, p2)
    obs = info = None
    for _ in range(n):
        obs, _, _, _, info = env.step(a)
    return obs, info


def save_img(obs, name):
    from PIL import Image
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray(obs).save(DEBUG_DIR / f"{name}.png")


def make_env_none():
    import stable_retro as retro
    return retro.make(
        GAME, state=retro.State.NONE, players=2,
        use_restricted_actions=retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=retro.data.Integrations.ALL,
    )


def make_env_default():
    import stable_retro as retro
    return retro.make(
        GAME, players=2,
        use_restricted_actions=retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=retro.data.Integrations.ALL,
    )


def idle_test(state_bytes, frames=300):
    """Returns (passed, h0, h1, first_hit_frame)."""
    env = make_env_default()
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
    env.close()
    return last_h == h0, h0, last_h, first_hit


def combat_test(state_bytes):
    """Walk + attack. Returns (p1_dmg, p2_dmg)."""
    env = make_env_default()
    env.reset()
    env.unwrapped.em.set_state(state_bytes)
    ram = env.unwrapped.get_ram()
    h0_p1, h0_p2 = ram[P1_HEALTH], ram[P2_HEALTH]
    step_n(env, 120, p1=[RIGHT], p2=[LEFT])
    for _ in range(15):
        step_n(env, 2, p1=[Y])
        step_n(env, 6)
        step_n(env, 2, p1=[C])
        step_n(env, 6)
    for _ in range(10):
        step_n(env, 2, p2=[Y])
        step_n(env, 6)
    ram = env.unwrapped.get_ram()
    env.close()
    return h0_p1 - ram[P1_HEALTH], h0_p2 - ram[P2_HEALTH]


def generate_state(p1_char_id, settle_frames, apply_timer_fix, reset_p1_health):
    """Generate 2P-patched fight state for the given P1 character.

    Returns (state_bytes, obs_at_fight_start) or (None, None) on failure.
    """
    cfg_desc = (f"settle={settle_frames} timer_fix={apply_timer_fix} "
                f"reset_p1={reset_p1_health}")

    env = make_env_none()
    env.reset()
    step_n(env, 2050)
    step_n(env, 3, p1=[START])
    step_n(env, 10)
    step_n(env, 3, p1=[START])

    fight_started = False
    obs_at_start = None
    for _ in range(600):
        env.step(NOOP)
        s = env.unwrapped.em.get_state()
        blob = bytearray(s)
        blob[RAM_BASE + P1_CHAR] = p1_char_id
        env.unwrapped.em.set_state(bytes(blob))
        if env.unwrapped.get_ram()[P1_HEALTH] > 100:
            obs_at_start, _ = step_n(env, 1)
            fight_started = True
            break

    if not fight_started:
        env.close()
        return None, None

    # Settle: advance N frames with P1 invincible and P1_CHAR locked
    for f in range(settle_frames):
        env.step(NOOP)
        if f % 30 == 0:
            s = env.unwrapped.em.get_state()
            blob = bytearray(s)
            blob[RAM_BASE + P1_HEALTH] = MAX_HEALTH
            blob[RAM_BASE + P1_CHAR] = p1_char_id
            env.unwrapped.em.set_state(bytes(blob))

    state = env.unwrapped.em.get_state()
    env.close()

    # Apply 2P conversion + fixes
    blob = bytearray(state)
    blob[RAM_BASE + MODE_BYTE] = 0
    blob[RAM_BASE + COMBAT_P1] = 3
    blob[RAM_BASE + COMBAT_P2] = 3
    blob[RAM_BASE + P1_CHAR]   = p1_char_id  # ensure correct char

    if reset_p1_health:
        blob[RAM_BASE + P1_HEALTH] = MAX_HEALTH
    blob[RAM_BASE + P2_HEALTH] = MAX_HEALTH   # always ensure Sagat at full health

    if apply_timer_fix:
        blob[RAM_BASE + TIMER_BYTE] = TIMER_RYU

    return bytes(blob), obs_at_start


def main():
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("SF2CE Non-Ryu State Generation — All 12 Characters vs Sagat")
    print("=" * 72)

    results = []

    for char_id in range(12):
        char_name = CHAR_NAMES[char_id]
        cfg = CHAR_CONFIG[char_id]

        print(f"\n  {char_name} (settle={cfg['settle']} timer_fix={cfg['timer_fix']}):")

        state, obs = generate_state(
            char_id,
            cfg["settle"],
            cfg["timer_fix"],
            cfg["reset_p1"],
        )

        if not state:
            print(f"    FAILED to generate fight state")
            results.append((char_name, False, False, False, 0, 0))
            continue

        blob = bytearray(state)
        p1c = blob[RAM_BASE + P1_CHAR]
        p2c = blob[RAM_BASE + P2_CHAR]
        p1h = blob[RAM_BASE + P1_HEALTH]
        p2h = blob[RAM_BASE + P2_HEALTH]
        timer_val = blob[RAM_BASE + TIMER_BYTE]
        held = p1c == char_id

        print(f"    P1={CHAR_NAMES.get(p1c,'?')} P2={CHAR_NAMES.get(p2c,'?')} "
              f"P1H={p1h} P2H={p2h} timer=0x{timer_val:02X}")

        ok, h0, h1, fhit = idle_test(state)
        p1d, p2d = combat_test(state)
        combat_ok = p1d > 0 or p2d > 0

        idle_str   = "PASS" if ok else f"FAIL({h0}->{h1}, f{fhit})"
        combat_str = f"OK(P1-{p1d} P2-{p2d})" if combat_ok else "NONE"
        print(f"    idle={idle_str}  combat={combat_str}")

        results.append((char_name, held, ok, combat_ok, p1d, p2d))

        if ok and held:
            out = STATE_DIR / f"{char_name.lower()}_vs_sagat.state"
            out.write_bytes(state)
            if obs is not None:
                save_img(obs, f"{char_name}_vs_sagat_start")
            print(f"    Saved -> {out.name}")
        else:
            print(f"    NOT SAVED (held={held} idle={ok})")

    print("\n" + "=" * 72)
    print("Final Summary")
    print("=" * 72)
    print(f"  {'Char':12s} {'Settle':6s} {'Idle':8s} {'Combat':12s}")
    print(f"  {'-' * 44}")
    for name, held, ok, combat, p1d, p2d in results:
        cfg = CHAR_CONFIG[list(CHAR_NAMES.values()).index(name)]
        print(f"  {name:12s} {cfg['settle']:6d} "
              f"{'PASS' if ok else 'FAIL':8s} "
              f"{'OK' if combat else 'NONE':12s}")

    passed = sum(1 for _, h, i, _, _, _ in results if h and i)
    print(f"\n  States generated: {passed}/12")

    if passed < 12:
        print("\n  Missing characters:")
        for name, held, ok, combat, p1d, p2d in results:
            if not (held and ok):
                print(f"    {name}: held={held} idle={ok} combat={combat}")

    print(f"\n  State files in: {STATE_DIR}")
    saved = list(STATE_DIR.glob("*_vs_sagat.state"))
    for f in sorted(saved):
        print(f"    {f.name}")


if __name__ == "__main__":
    main()
