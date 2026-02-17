#!/usr/bin/env python3
"""
Live match viewer — watch AI agents fight in real-time.

Opens a pygame window showing the emulation with HUD overlay
(health bars, round info, input display, FPS).

Usage (from WSL2):
    # Random actions — verify emulation works
    python3 scripts/watch_match.py

    # Load a trained model for P1
    python3 scripts/watch_match.py --p1 models/my_fighter.zip

    # Both players with models
    python3 scripts/watch_match.py --p1 models/a.zip --p2 models/b.zip

    # Slow down to watch (default 60fps)
    python3 scripts/watch_match.py --fps 30

    # Save recording to MP4
    python3 scripts/watch_match.py --record match.mp4

    # Run for N frames then exit
    python3 scripts/watch_match.py --frames 1800

Requirements (WSL2):
    pip3 install stable-retro pygame numpy
    # For recording: pip3 install opencv-python-headless
    # For models:    pip3 install stable-baselines3

Controls:
    Q / ESC     Quit
    SPACE       Pause / Resume
    R           Reset environment
    S           Screenshot (saves PNG)
    +/=         Speed up
    -           Slow down

Note: Requires WSLg (Windows 11) for display from WSL2.
"""

import argparse
import sys
import time
from collections import deque

import numpy as np
import pygame
import stable_retro

GAME = "StreetFighterIISpecialChampionEdition-Genesis-v0"
MAX_HEALTH = 176  # SF2 Champion Edition
WINDOW_SCALE = 3
SIDEBAR_WIDTH = 160   # Vertical panel per player (left=P1, right=P2)
BOTTOM_BAR_HEIGHT = 22  # Thin info strip at bottom

# Genesis button layout from stable-retro FILTERED:
# Index: 0=B, 1=A, 2=MODE, 3=START, 4=UP, 5=DOWN, 6=LEFT, 7=RIGHT, 8=C, 9=Y, 10=X, 11=Z
# Per player (P1 = indices 0-11, P2 = indices 12-23)
BUTTON_NAMES = ["B", "A", "MODE", "START", "UP", "DOWN", "LEFT", "RIGHT", "C", "Y", "X", "Z"]
# Friendly display names for SF2 mapping
DISPLAY_NAMES = ["LK", "MK", "MODE", "START", "UP", "DOWN", "LEFT", "RIGHT", "HK", "LP", "MP", "HP"]
DPAD_INDICES = {"UP": 4, "DOWN": 5, "LEFT": 6, "RIGHT": 7}
# SF2 button mapping: Y=LP, X=MP, Z=HP (punches top), B=LK, A=MK, C=HK (kicks bottom)
ATTACK_BUTTONS = [
    {"idx": 9, "label": "LP", "row": 0, "col": 0},  # Y = Light Punch
    {"idx": 10, "label": "MP", "row": 0, "col": 1},  # X = Medium Punch
    {"idx": 11, "label": "HP", "row": 0, "col": 2},  # Z = Hard Punch
    {"idx": 0, "label": "LK", "row": 1, "col": 0},   # B = Light Kick
    {"idx": 1, "label": "MK", "row": 1, "col": 1},   # A = Medium Kick
    {"idx": 8, "label": "HK", "row": 1, "col": 2},   # C = Hard Kick
]


class InputTracker:
    """Tracks and logs button presses for both players."""

    def __init__(self, log_file=None, max_recent=25):
        self.p1_counts = np.zeros(12, dtype=np.int64)
        self.p2_counts = np.zeros(12, dtype=np.int64)
        self.p1_prev = np.zeros(12, dtype=np.int8)
        self.p2_prev = np.zeros(12, dtype=np.int8)
        self.total_frames = 0
        self.p1_recent = deque(maxlen=max_recent)
        self.p2_recent = deque(maxlen=max_recent)
        self._log_file = None
        if log_file:
            self._log_file = open(log_file, "w")
            header = "frame," + ",".join(f"p1_{n}" for n in DISPLAY_NAMES) + "," + ",".join(f"p2_{n}" for n in DISPLAY_NAMES)
            self._log_file.write(header + "\n")

    def update(self, action, frame_num):
        """Record one frame of input. Print new button presses to console."""
        p1 = np.array(action[:12], dtype=np.int8)
        p2 = np.array(action[12:], dtype=np.int8)

        self.p1_counts += p1
        self.p2_counts += p2
        self.total_frames += 1

        # Detect newly pressed buttons (0→1 transitions)
        p1_new = p1 & ~self.p1_prev
        p2_new = p2 & ~self.p2_prev

        parts = []
        if p1_new.any():
            btns = [DISPLAY_NAMES[i] for i in range(12) if p1_new[i]]
            combo = "+".join(btns)
            parts.append(f"P1: {combo}")
            self.p1_recent.append((frame_num, combo))
        if p2_new.any():
            btns = [DISPLAY_NAMES[i] for i in range(12) if p2_new[i]]
            combo = "+".join(btns)
            parts.append(f"P2: {combo}")
            self.p2_recent.append((frame_num, combo))
        if parts:
            print(f"  [{frame_num:>6}] {'   '.join(parts)}")

        self.p1_prev = p1
        self.p2_prev = p2

        # Write to CSV log
        if self._log_file:
            row = f"{frame_num}," + ",".join(str(int(x)) for x in p1) + "," + ",".join(str(int(x)) for x in p2)
            self._log_file.write(row + "\n")

    def print_summary(self):
        """Print end-of-match button press statistics."""
        print("\n  " + "=" * 56)
        print("  INPUT SUMMARY")
        print("  " + "=" * 56)
        print(f"  Total frames: {self.total_frames}\n")

        # Header
        print(f"  {'Button':<8} {'P1 Presses':>12} {'P1 %':>8}  {'P2 Presses':>12} {'P2 %':>8}")
        print(f"  {'─'*8} {'─'*12} {'─'*8}  {'─'*12} {'─'*8}")

        for i in range(12):
            name = DISPLAY_NAMES[i]
            p1_c = int(self.p1_counts[i])
            p2_c = int(self.p2_counts[i])
            p1_pct = (p1_c / self.total_frames * 100) if self.total_frames else 0
            p2_pct = (p2_c / self.total_frames * 100) if self.total_frames else 0
            print(f"  {name:<8} {p1_c:>12,} {p1_pct:>7.1f}%  {p2_c:>12,} {p2_pct:>7.1f}%")

        # Totals
        p1_total = int(self.p1_counts.sum())
        p2_total = int(self.p2_counts.sum())
        print(f"  {'─'*8} {'─'*12} {'─'*8}  {'─'*12} {'─'*8}")
        print(f"  {'TOTAL':<8} {p1_total:>12,}           {p2_total:>12,}")

        # Most pressed
        p1_top = DISPLAY_NAMES[int(np.argmax(self.p1_counts))]
        p2_top = DISPLAY_NAMES[int(np.argmax(self.p2_counts))]
        print(f"\n  P1 most pressed: {p1_top}  |  P2 most pressed: {p2_top}")
        print("  " + "=" * 56)

    def close(self):
        if self._log_file:
            self._log_file.close()
            print(f"  Input log saved: {self._log_file.name}")


def load_model(path: str):
    """Load an SB3 model checkpoint."""
    try:
        from stable_baselines3 import PPO
        print(f"  Loading model: {path}")
        model = PPO.load(path)
        print(f"  Model loaded OK")
        return model
    except ImportError:
        print("ERROR: stable-baselines3 not installed.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load '{path}': {e}")
        sys.exit(1)


def get_action(model, obs, env):
    """Get action from model or random (12 buttons per player)."""
    if model is not None:
        action, _ = model.predict(obs, deterministic=True)
        return action
    return env.action_space.sample()[:12]


def draw_dpad(surface, x, y, size, directions):
    """Draw a d-pad showing active directions.

    Args:
        directions: dict with UP/DOWN/LEFT/RIGHT as bools
    """
    s = size  # size of each d-pad segment
    gap = 1
    inactive = (50, 50, 60)
    active = (60, 220, 60)

    # Center block
    cx, cy = x + s + gap, y + s + gap

    # Up
    color = active if directions.get("UP") else inactive
    pygame.draw.rect(surface, color, (cx, cy - s - gap, s, s))
    # Down
    color = active if directions.get("DOWN") else inactive
    pygame.draw.rect(surface, color, (cx, cy + s + gap, s, s))
    # Left
    color = active if directions.get("LEFT") else inactive
    pygame.draw.rect(surface, color, (cx - s - gap, cy, s, s))
    # Right
    color = active if directions.get("RIGHT") else inactive
    pygame.draw.rect(surface, color, (cx + s + gap, cy, s, s))
    # Center dot
    pygame.draw.rect(surface, (35, 35, 45), (cx, cy, s, s))


def draw_attack_buttons(surface, x, y, btn_size, action_arr):
    """Draw 6 attack buttons in a 3x2 grid (punches top, kicks bottom)."""
    gap = 3
    inactive = (50, 50, 60)
    # Colors: light=yellow, medium=orange, hard=red
    punch_colors = [(220, 200, 60), (220, 140, 40), (220, 60, 60)]
    kick_colors = [(60, 180, 220), (60, 120, 220), (120, 60, 220)]

    font = pygame.font.SysFont("monospace", 10, bold=True)

    for btn in ATTACK_BUTTONS:
        bx = x + btn["col"] * (btn_size + gap)
        by = y + btn["row"] * (btn_size + gap)
        pressed = bool(action_arr[btn["idx"]])

        if pressed:
            if btn["row"] == 0:
                color = punch_colors[btn["col"]]
            else:
                color = kick_colors[btn["col"]]
        else:
            color = inactive

        pygame.draw.rect(surface, color, (bx, by, btn_size, btn_size), border_radius=3)

        # Label
        label_color = (20, 20, 30) if pressed else (90, 90, 100)
        label = font.render(btn["label"], True, label_color)
        lx = bx + (btn_size - label.get_width()) // 2
        ly = by + (btn_size - label.get_height()) // 2
        surface.blit(label, (lx, ly))


def draw_player_sidebar(surface, x, y, width, height, health_pct, wins, action_12, label, color, recent_log):
    """Draw one player's vertical sidebar panel with input log."""
    # Background
    pygame.draw.rect(surface, (20, 20, 30), (x, y, width, height))

    margin = 10
    cx = x + margin
    usable_w = width - margin * 2

    font_sm = pygame.font.SysFont("monospace", 12, bold=True)
    font_md = pygame.font.SysFont("monospace", 16, bold=True)
    font_lg = pygame.font.SysFont("monospace", 22, bold=True)
    font_log = pygame.font.SysFont("monospace", 10)

    # Player label (centered)
    lbl = font_lg.render(label, True, color)
    surface.blit(lbl, (x + width // 2 - lbl.get_width() // 2, y + 12))

    # Health bar
    bar_y = y + 45
    bar_h = 16
    pygame.draw.rect(surface, (40, 40, 50), (cx, bar_y, usable_w, bar_h))
    pygame.draw.rect(surface, color, (cx, bar_y, int(usable_w * health_pct), bar_h))
    pygame.draw.rect(surface, (100, 100, 120), (cx, bar_y, usable_w, bar_h), 1)

    # Health percentage (centered)
    pct = font_md.render(f"{int(health_pct * 100)}%", True, color)
    surface.blit(pct, (x + width // 2 - pct.get_width() // 2, bar_y + bar_h + 4))

    # Wins
    wins_y = bar_y + bar_h + 28
    wins_txt = font_sm.render(f"Wins: {wins}", True, (160, 160, 170))
    surface.blit(wins_txt, (cx, wins_y))

    # Divider
    div_y = wins_y + 20
    pygame.draw.line(surface, (50, 50, 60), (cx, div_y), (x + width - margin, div_y), 1)

    # D-pad + attack buttons
    input_y = div_y + 8
    dirs = {d: bool(action_12[i]) for d, i in DPAD_INDICES.items()}
    draw_dpad(surface, cx, input_y, 13, dirs)
    draw_attack_buttons(surface, cx + 52, input_y, 18, action_12)

    # START indicator
    if action_12[3]:
        st = font_sm.render("ST", True, (255, 255, 100))
        surface.blit(st, (cx, input_y + 50))

    # --- Input log section ---
    log_y = input_y + 68
    pygame.draw.line(surface, (50, 50, 60), (cx, log_y), (x + width - margin, log_y), 1)

    log_header = font_sm.render("INPUT LOG", True, (100, 100, 110))
    surface.blit(log_header, (cx, log_y + 4))

    line_h = 13
    log_start_y = log_y + 20
    max_lines = (height - (log_start_y - y) - 5) // line_h

    # Draw recent presses (newest at bottom, scrolls up)
    entries = list(recent_log)
    visible = entries[-max_lines:] if len(entries) > max_lines else entries
    for i, (fnum, combo) in enumerate(visible):
        # Fade older entries
        age = len(visible) - 1 - i
        brightness = max(60, 200 - age * 6)
        txt_color = (brightness, brightness, brightness + 20)
        line = font_log.render(f"{fnum:>5} {combo}", True, txt_color)
        surface.blit(line, (cx, log_start_y + i * line_h))

    # Inner border (green accent on the edge facing the game)
    bx = (x + width - 1) if label == "P1" else x
    pygame.draw.line(surface, (60, 200, 60), (bx, y), (bx, y + height), 2)


def draw_hud(surface, info, frame_num, fps, paused, speed, action, tracker=None):
    """Draw P1 sidebar (left), P2 sidebar (right), and bottom info bar."""
    w = surface.get_width()
    h = surface.get_height()
    game_h = h - BOTTOM_BAR_HEIGHT

    # Game state
    p1_health = info.get("health", 0)
    p2_health = info.get("enemy_health", 0)
    p1_pct = max(0, min(1, p1_health / MAX_HEALTH))
    p2_pct = max(0, min(1, p2_health / MAX_HEALTH))
    p1_wins = info.get("matches_won", 0)
    p2_wins = info.get("enemy_matches_won", 0)

    p1_action = action[:12] if action is not None else np.zeros(12, dtype=np.int8)
    p2_action = action[12:] if action is not None else np.zeros(12, dtype=np.int8)

    p1_log = tracker.p1_recent if tracker else []
    p2_log = tracker.p2_recent if tracker else []

    # P1 sidebar (left)
    draw_player_sidebar(surface, 0, 0, SIDEBAR_WIDTH, game_h, p1_pct, p1_wins, p1_action, "P1", (80, 180, 255), p1_log)

    # P2 sidebar (right)
    draw_player_sidebar(surface, w - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, game_h, p2_pct, p2_wins, p2_action, "P2", (255, 80, 80), p2_log)

    # Bottom info bar
    bar_y = game_h
    pygame.draw.rect(surface, (20, 20, 30), (0, bar_y, w, BOTTOM_BAR_HEIGHT))
    pygame.draw.line(surface, (60, 200, 60), (0, bar_y), (w, bar_y), 1)

    font_sm = pygame.font.SysFont("monospace", 12)
    timer = info.get("continuetimer", 0)
    score = info.get("score", 0)

    left_txt = font_sm.render(f"Timer: {timer}  Score: {score}", True, (140, 140, 150))
    right_txt = font_sm.render(f"Frame: {frame_num}  {fps:.0f} FPS  {speed:.1f}x", True, (140, 140, 150))
    surface.blit(left_txt, (15, bar_y + 4))
    surface.blit(right_txt, (w - right_txt.get_width() - 15, bar_y + 4))

    # Pause overlay (centered on game area)
    if paused:
        font_lg = pygame.font.SysFont("monospace", 24, bold=True)
        pause_text = font_lg.render("PAUSED", True, (255, 50, 50))
        game_cx = SIDEBAR_WIDTH + (w - SIDEBAR_WIDTH * 2) // 2
        surface.blit(pause_text, (game_cx - pause_text.get_width() // 2, game_h // 2))


def main():
    parser = argparse.ArgumentParser(description="Watch AI agents fight in real-time")
    parser.add_argument("--p1", type=str, default=None, help="P1 model checkpoint (.zip)")
    parser.add_argument("--p2", type=str, default=None, help="P2 model checkpoint (.zip)")
    parser.add_argument("--fps", type=int, default=60, help="Target FPS (default: 60)")
    parser.add_argument("--frames", type=int, default=0, help="Max frames (0=unlimited)")
    parser.add_argument("--record", type=str, default=None, help="Record to MP4 file")
    parser.add_argument("--log", type=str, default=None, help="Save frame-by-frame input log to CSV")
    parser.add_argument("--scale", type=int, default=WINDOW_SCALE, help="Window scale (default: 3)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Rawl Match Viewer")
    print("=" * 60)

    # Load models
    print("\n[1/3] Loading agents...")
    model_p1 = load_model(args.p1) if args.p1 else None
    model_p2 = load_model(args.p2) if args.p2 else None
    has_model = model_p1 or model_p2

    if not has_model:
        print("  No models — random actions for both players")
    else:
        if not model_p1:
            print("  P1: random actions")
        if not model_p2:
            print("  P2: random actions")

    # Create environment
    print("\n[2/3] Starting emulation...")
    env = stable_retro.make(
        GAME,
        players=2,
        use_restricted_actions=stable_retro.Actions.FILTERED,
        render_mode="rgb_array",
        inttype=stable_retro.data.Integrations.ALL,
    )
    obs, info = env.reset()
    native_h, native_w = obs.shape[:2]
    print(f"  Game: {GAME}")
    print(f"  Frame: {native_w}x{native_h}  |  Actions: {env.action_space}")
    print(f"  Buttons: {env.buttons}")

    # Setup pygame — game in center, sidebars on left/right
    game_w = native_w * args.scale
    game_h = native_h * args.scale
    display_w = SIDEBAR_WIDTH + game_w + SIDEBAR_WIDTH
    display_h = game_h + BOTTOM_BAR_HEIGHT
    pygame.init()
    screen = pygame.display.set_mode((display_w, display_h))
    pygame.display.set_caption("Rawl Match Viewer")
    clock = pygame.time.Clock()

    # Setup recorder
    recorder = None
    if args.record:
        try:
            import cv2
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            recorder = cv2.VideoWriter(args.record, fourcc, args.fps, (display_w, display_h))
            print(f"  Recording to: {args.record}")
        except ImportError:
            print("  WARNING: opencv-python-headless not installed, skipping recording")

    # Setup input tracker
    tracker = InputTracker(log_file=args.log)

    print(f"\n[3/3] Running at {args.fps} FPS (scale: {args.scale}x)")
    print("  Controls: Q/ESC=quit  SPACE=pause  R=reset  S=screenshot  +/-=speed\n")

    # Main loop
    frame_num = 0
    paused = False
    speed = 1.0
    fps_counter = 0
    fps_timer = time.time()
    measured_fps = 0.0
    running = True
    current_action = np.zeros(24, dtype=np.int8)

    while running:
        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                    print(f"  {'PAUSED' if paused else 'RESUMED'}")
                elif event.key == pygame.K_r:
                    obs, info = env.reset()
                    frame_num = 0
                    print("  RESET")
                elif event.key == pygame.K_s:
                    fname = f"rawl_screenshot_{frame_num:06d}.png"
                    pygame.image.save(screen, fname)
                    print(f"  Screenshot: {fname}")
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    speed = min(4.0, speed + 0.5)
                    print(f"  Speed: {speed:.1f}x")
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = max(0.25, speed - 0.5)
                    print(f"  Speed: {speed:.1f}x")

        if paused:
            # Still render while paused (shows PAUSED text + last input state)
            draw_hud(screen, info, frame_num, measured_fps, paused, speed, current_action, tracker)
            pygame.display.flip()
            clock.tick(20)
            continue

        # Step environment
        if has_model:
            p1_action = get_action(model_p1, obs, env)
            p2_action = get_action(model_p2, obs, env)
            action = np.concatenate([p1_action, p2_action])
        else:
            action = env.action_space.sample()

        current_action = action
        obs, reward, terminated, truncated, info = env.step(action)
        frame_num += 1
        tracker.update(action, frame_num)

        # Render game frame
        game_surface = pygame.surfarray.make_surface(
            np.transpose(obs, (1, 0, 2))  # HWC -> WHC for pygame
        )
        game_surface = pygame.transform.scale(game_surface, (game_w, game_h))

        # Compose display — game centered between sidebars
        screen.fill((20, 20, 30))
        screen.blit(game_surface, (SIDEBAR_WIDTH, 0))
        draw_hud(screen, info, frame_num, measured_fps, paused, speed, current_action, tracker)

        pygame.display.flip()

        # Record
        if recorder is not None:
            import cv2
            frame_data = pygame.surfarray.array3d(screen)
            frame_bgr = cv2.cvtColor(np.transpose(frame_data, (1, 0, 2)), cv2.COLOR_RGB2BGR)
            recorder.write(frame_bgr)

        # Episode end
        if terminated or truncated:
            print(f"  Episode ended at frame {frame_num} — resetting")
            obs, info = env.reset()

        # FPS
        fps_counter += 1
        now = time.time()
        if now - fps_timer >= 1.0:
            measured_fps = fps_counter / (now - fps_timer)
            fps_counter = 0
            fps_timer = now

        # Frame limit
        if args.frames > 0 and frame_num >= args.frames:
            print(f"\n  Reached {args.frames} frame limit")
            break

        # Frame pacing
        clock.tick(int(args.fps * speed))

    # Cleanup
    if recorder is not None:
        recorder.release()
        print(f"  Recording saved: {args.record}")

    env.close()
    pygame.quit()

    tracker.print_summary()
    tracker.close()
    print("=" * 60)


if __name__ == "__main__":
    main()
