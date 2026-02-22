from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from rawl.config import settings
from rawl.engine.emulation.base import EmulationEngine
from rawl.game_adapters.base import GameAdapter

logger = logging.getLogger(__name__)

# Directory containing custom stable-retro integration files
_INTEGRATIONS_DIR = Path(__file__).parent / "integrations"

# Base directory containing per-game state subdirectories (states/{game_id}/)
_STATES_BASE_DIR = Path(__file__).parent / "states"

# Track whether we've already provisioned the ROM this process
_rom_provisioned = False

# ---------------------------------------------------------------------------
# SF2CE VS Battle character select grid (2 rows × 6 cols, wrapping)
# ---------------------------------------------------------------------------
# Row 0: Ryu  Honda  Blanka  Guile  Vega   Bison
# Row 1: Ken  ChunLi Zangief Dhalsim Sagat Balrog
# P1 cursor starts at Ryu (row=0, col=0)
# P2 cursor starts at Ken (row=1, col=0)
_SF2CE_GRID = [
    ["Ryu", "Honda", "Blanka", "Guile", "Vega", "Bison"],
    ["Ken", "ChunLi", "Zangief", "Dhalsim", "Sagat", "Balrog"],
]
_SF2CE_CHAR_POS: dict[str, tuple[int, int]] = {}  # name -> (row, col)
for _r, _row in enumerate(_SF2CE_GRID):
    for _c, _name in enumerate(_row):
        _SF2CE_CHAR_POS[_name.lower()] = (_r, _c)

# Button indices in MultiBinary(24): first 12 = P1, next 12 = P2
_B, _A, _MODE, _START, _UP, _DOWN, _LEFT, _RIGHT, _C, _Y, _X, _Z = range(12)
_GRID_COLS = 6


class RetroEngine(EmulationEngine):
    """stable-retro emulation engine using Genesis (SF2 Champion Edition).

    Wraps a ``retro.RetroEnv`` and translates between stable-retro's flat
    observation/action/info format and the nested dict format expected by
    game adapters (formerly provided by DIAMBRA).

    One emulator instance per process — the emulation worker spawns one Process per match.
    """

    def __init__(
        self,
        game_id: str,
        match_id: str,
        adapter: GameAdapter | None = None,
        p1_character: str = "",
        p2_character: str = "",
    ) -> None:
        self.game_id = game_id
        self.match_id = match_id
        self._adapter = adapter
        self._p1_character = p1_character
        self._p2_character = p2_character
        self._env = None
        self._obs_size: int = settings.retro_obs_size
        self._nav_frames: list[np.ndarray] = []
        self._charselect_bytes: bytes | None = None
        # Derive a per-match seed from match_id so each match is unique but reproducible
        self._seed: int = int(hashlib.sha256(match_id.encode()).hexdigest()[:8], 16)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Create env and load charselect state. Does NOT navigate to fight.

        Call ``navigate_to_fight()`` after starting the encoder so the
        character-select navigation is visible in the live stream.
        """
        import stable_retro as retro

        logger.info(
            "Starting RetroEngine",
            extra={"game_id": self.game_id, "match_id": self.match_id},
        )

        # Auto-provision ROM from S3 if not already present
        self._ensure_rom(retro)

        # Register custom integration data if configured
        integration_path = self._integration_path()
        if integration_path and integration_path.is_dir():
            retro.data.Integrations.add_custom_path(str(integration_path))
            logger.debug("Registered custom integration: %s", integration_path)

        make_kwargs: dict[str, Any] = {
            "game": settings.retro_game,
            "players": 2,
            "use_restricted_actions": retro.Actions.ALL,
            "render_mode": "rgb_array",
            "inttype": retro.data.Integrations.ALL,
        }

        self._env = retro.make(**make_kwargs)
        raw_obs, raw_info = self._env.reset(seed=self._seed)

        # Load charselect state (just set emulator state, don't navigate yet)
        self._charselect_bytes = self._load_charselect_state()
        if self._charselect_bytes is not None:
            self._env.unwrapped.em.set_state(self._charselect_bytes)
            noop = np.zeros(self._env.action_space.shape, dtype=np.int8)
            for _ in range(30):
                raw_obs, _, _, _, raw_info = self._env.step(noop)
        else:
            logger.warning(
                "No charselect state found — using default env state",
                extra={"match_id": self.match_id},
            )

        logger.info(
            "RetroEngine started (charselect loaded)",
            extra={
                "match_id": self.match_id,
                "seed": self._seed,
                "p1_character": self._p1_character or "default",
                "p2_character": self._p2_character or "default",
            },
        )
        return self._translate_obs(raw_obs), self._translate_info(raw_info)

    def navigate_to_fight(self) -> tuple[dict[str, np.ndarray], dict[str, Any], list[np.ndarray]]:
        """Navigate charselect menus to start fight. Returns captured frames.

        Returns (obs, info, nav_frames) where nav_frames is a list of raw
        RGB arrays (obs_size × obs_size) captured during navigation for
        streaming to viewers.
        """
        if self._env is None:
            raise RuntimeError("RetroEngine not started — call start() first")
        if self._charselect_bytes is None:
            # No charselect state — already at fight
            noop = np.zeros(self._env.action_space.shape, dtype=np.int8)
            raw_obs, _, _, _, raw_info = self._env.step(noop)
            return self._translate_obs(raw_obs), self._translate_info(raw_info), []

        raw_obs, raw_info = self._navigate_charselect(
            self._p1_character,
            self._p2_character,
        )
        nav_frames = self._nav_frames
        self._nav_frames = []
        return self._translate_obs(raw_obs), self._translate_info(raw_info), nav_frames

    def step(
        self, action: dict[str, np.ndarray]
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        if self._env is None:
            raise RuntimeError("RetroEngine not started — call start() first")

        flat_action = self._translate_action(action)
        raw_obs, reward, terminated, truncated, raw_info = self._env.step(flat_action)
        return (
            self._translate_obs(raw_obs),
            reward,
            terminated,
            truncated,
            self._translate_info(raw_info),
        )

    def stop(self) -> None:
        if self._env is not None:
            logger.info(
                "Stopping RetroEngine",
                extra={"match_id": self.match_id},
            )
            try:
                self._env.close()
            except Exception:
                logger.exception("Error closing RetroEngine")
            self._env = None

    # ------------------------------------------------------------------
    # Character select navigation
    # ------------------------------------------------------------------

    def _load_charselect_state(self) -> bytes | None:
        """Load the VS Battle character-select save state from disk."""
        states_dir = _STATES_BASE_DIR / self.game_id
        path = states_dir / "charselect.state"
        if path.is_file():
            return path.read_bytes()
        logger.warning("charselect.state not found at %s", path)
        return None

    def _navigate_charselect(
        self,
        p1_char: str,
        p2_char: str,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Move cursors to select characters and start fight.

        Charselect state must already be loaded (by ``start()``).
        Captures frames into ``self._nav_frames`` for live streaming.

        The game handles round transitions natively in VS Battle mode (bo3).
        """
        env = self._env
        self._nav_frames = []

        # Move P1 cursor (starts at Ryu = row 0, col 0)
        p1_target = _SF2CE_CHAR_POS.get(p1_char.lower())
        if p1_target is not None:
            self._move_cursor(p1_target, start_row=0, start_col=0, player=1)
        else:
            logger.warning("Unknown P1 character %r, using default (Ryu)", p1_char)

        # P1 confirms with START
        self._press_button(_START, player=1, hold=5)
        self._step_noop(60)

        # Move P2 cursor (starts at Ken = row 1, col 0)
        p2_target = _SF2CE_CHAR_POS.get(p2_char.lower())
        if p2_target is not None:
            self._move_cursor(p2_target, start_row=1, start_col=0, player=2)
        else:
            logger.warning("Unknown P2 character %r, using default (Ken)", p2_char)

        # P2 confirms with START
        self._press_button(_START, player=2, hold=5)
        self._step_noop(120)

        # Stage select — confirm with P1 START
        self._press_button(_START, player=1, hold=5)
        self._step_noop(300)

        # Verify fight loaded (health should be 176)
        ram = env.unwrapped.get_ram()
        p1h, p2h = ram[0x8042], ram[0x82C2]
        if p1h < 100:
            logger.error(
                "Fight did not load after charselect navigation: P1H=%d P2H=%d",
                p1h, p2h,
            )

        # Step a few noop frames so the first observation has valid video
        noop = np.zeros(env.action_space.shape, dtype=np.int8)
        raw_obs = None
        raw_info = None
        for _ in range(30):
            raw_obs, _, _, _, raw_info = env.step(noop)
            self._capture_nav_frame(raw_obs)

        logger.info(
            "Character select navigation complete",
            extra={
                "match_id": self.match_id,
                "p1": p1_char,
                "p2": p2_char,
                "p1_health": int(p1h),
                "p2_health": int(p2h),
                "nav_frames": len(self._nav_frames),
            },
        )
        return raw_obs, raw_info

    def _move_cursor(
        self,
        target: tuple[int, int],
        start_row: int,
        start_col: int,
        player: int,
    ) -> None:
        """Move a player's cursor from (start_row, start_col) to target (row, col).

        The grid is 2 rows × 6 cols and wraps horizontally.
        UP/DOWN toggles between row 0 and row 1.
        """
        target_row, target_col = target

        # Vertical: only 2 rows, so one DOWN or UP if needed
        if target_row != start_row:
            direction = _DOWN if target_row > start_row else _UP
            self._press_button(direction, player=player, hold=3)
            self._step_noop(10)

        # Horizontal: find shortest path (grid wraps)
        col_diff = (target_col - start_col) % _GRID_COLS
        if col_diff == 0:
            return
        if col_diff <= _GRID_COLS // 2:
            # Move right
            for _ in range(col_diff):
                self._press_button(_RIGHT, player=player, hold=3)
                self._step_noop(10)
        else:
            # Move left (shorter path)
            left_steps = _GRID_COLS - col_diff
            for _ in range(left_steps):
                self._press_button(_LEFT, player=player, hold=3)
                self._step_noop(10)

    def _press_button(self, button: int, player: int = 1, hold: int = 5) -> None:
        """Press a single button for *hold* frames."""
        action = np.zeros(self._env.action_space.shape, dtype=np.int8)
        offset = 0 if player == 1 else 12
        action[offset + button] = 1
        for _ in range(hold):
            raw_obs, _, _, _, _ = self._env.step(action)
            self._capture_nav_frame(raw_obs)

    def _step_noop(self, frames: int) -> None:
        """Step the emulator with no input for *frames* frames."""
        noop = np.zeros(self._env.action_space.shape, dtype=np.int8)
        for _ in range(frames):
            raw_obs, _, _, _, _ = self._env.step(noop)
            self._capture_nav_frame(raw_obs)

    def _capture_nav_frame(self, raw_obs: np.ndarray) -> None:
        """Capture a navigation frame (resized) for live streaming."""
        resized = cv2.resize(raw_obs, (self._obs_size, self._obs_size))
        self._nav_frames.append(resized)

    # ------------------------------------------------------------------
    # Format translation
    # ------------------------------------------------------------------

    def _translate_obs(self, raw_obs: np.ndarray) -> dict[str, np.ndarray]:
        """Resize frame to obs_size x obs_size; flip horizontally for P2."""
        resized = cv2.resize(raw_obs, (self._obs_size, self._obs_size))
        p2_frame = cv2.flip(resized, 1)  # horizontal flip for P2 perspective
        return {"P1": resized, "P2": p2_frame}

    def _translate_info(self, raw_info: dict[str, Any]) -> dict[str, Any]:
        """Re-nest stable-retro's flat info dict into adapter-expected format.

        Handles two naming conventions:
          - SF2 Genesis style:  health, enemy_health, matches_won, enemy_matches_won,
                                continuetimer
          - Prefixed style:     p1_health, p2_health, p1_round_wins, ..., time
        """
        info: dict[str, Any] = {"P1": {}, "P2": {}}

        # --- SF2 Genesis flat keys (no prefix) ---
        if "health" in raw_info and "enemy_health" in raw_info:
            info["P1"]["health"] = raw_info["health"]
            info["P2"]["health"] = raw_info["enemy_health"]
            info["P1"]["round_wins"] = raw_info.get("matches_won", 0)
            info["P2"]["round_wins"] = raw_info.get("enemy_matches_won", 0)
            info["timer"] = raw_info.get("continuetimer", 0)
            # Pass through any extra keys
            _handled = {
                "health", "enemy_health", "matches_won", "enemy_matches_won",
                "continuetimer",
            }
            for key, val in raw_info.items():
                if key not in _handled:
                    info[key] = val
        else:
            # --- Prefixed style (p1_*, p2_*, time) ---
            for key, val in raw_info.items():
                if key.startswith("p1_"):
                    info["P1"][key[3:]] = val
                elif key.startswith("p2_"):
                    info["P2"][key[3:]] = val
                elif key == "time":
                    info["timer"] = val
                else:
                    info[key] = val
            # Normalize round_wins
            info["P1"]["round_wins"] = info["P1"].pop("round_wins", 0)
            info["P2"]["round_wins"] = info["P2"].pop("round_wins", 0)

        # Derive current round number (1-indexed)
        p1_wins = info["P1"].get("round_wins", 0)
        p2_wins = info["P2"].get("round_wins", 0)
        info["round"] = p1_wins + p2_wins + 1

        # Ensure adapters always see required fields in player dicts.
        for player in ("P1", "P2"):
            info[player].setdefault("health", 0)
            info[player].setdefault("stage_side", 0)
            info[player].setdefault("combo_count", 0)
            info[player]["round"] = info["round"]
            info[player]["timer"] = info.get("timer", 0)

        return info

    def _translate_action(self, action_dict: dict[str, np.ndarray]) -> np.ndarray:
        """Convert {"P1": array, "P2": array} to flat concatenated array."""
        p1_action = action_dict["P1"]
        p2_action = (
            self._adapter.mirror_action(action_dict["P2"])
            if self._adapter is not None
            else action_dict["P2"]
        )
        flat = np.concatenate([p1_action, p2_action])
        # Mask START buttons to prevent game pauses during fights.
        # Actions.ALL is needed for charselect navigation but START must
        # be suppressed during gameplay.
        flat[_START] = 0        # P1 START
        flat[12 + _START] = 0   # P2 START
        return flat

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_rom(self, retro) -> None:
        """Download ROM from S3 into stable-retro's data dir if not present.

        Uses sync boto3 (not async aioboto3) because this runs inside an
        already-running asyncio event loop.
        """
        global _rom_provisioned
        if _rom_provisioned:
            return

        game_path = Path(retro.data.path()) / "stable" / settings.retro_game
        rom_path = game_path / "rom.md"

        if rom_path.exists():
            logger.info("ROM already present at %s", rom_path)
            _rom_provisioned = True
            return

        logger.info("ROM not found — downloading from S3: %s", settings.retro_rom_s3_key)
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        try:
            resp = client.get_object(Bucket=settings.s3_bucket, Key=settings.retro_rom_s3_key)
            rom_data = resp["Body"].read()
        except Exception as e:
            raise FileNotFoundError(
                f"ROM not found in S3 at key '{settings.retro_rom_s3_key}': {e}. "
                "Upload the ROM first: scripts/upload_rom.py"
            ) from e

        game_path.mkdir(parents=True, exist_ok=True)
        rom_path.write_bytes(rom_data)
        logger.info("ROM provisioned: %s (%d bytes)", rom_path, len(rom_data))
        _rom_provisioned = True

    def _integration_path(self) -> Path | None:
        """Resolve the custom integration directory for this game.

        SF2 Genesis uses built-in integration — no custom path needed.
        """
        if settings.retro_integration_path:
            return Path(settings.retro_integration_path)
        return None
