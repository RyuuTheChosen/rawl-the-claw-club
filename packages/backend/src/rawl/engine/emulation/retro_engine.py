from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from rawl.config import settings
from rawl.engine.emulation.base import EmulationEngine

logger = logging.getLogger(__name__)

# Directory containing custom stable-retro integration files
_INTEGRATIONS_DIR = Path(__file__).parent / "integrations"

# Track whether we've already provisioned the ROM this process
_rom_provisioned = False


class RetroEngine(EmulationEngine):
    """stable-retro emulation engine using Genesis (SF2 Champion Edition).

    Wraps a ``retro.RetroEnv`` and translates between stable-retro's flat
    observation/action/info format and the nested dict format expected by
    game adapters (formerly provided by DIAMBRA).

    One emulator instance per process — Celery prefork workers guarantee this.
    """

    def __init__(self, game_id: str, match_id: str) -> None:
        self.game_id = game_id
        self.match_id = match_id
        self._env = None
        self._obs_size: int = settings.retro_obs_size

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        import retro

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

        self._env = retro.make(
            settings.retro_game,
            players=2,
            use_restricted_actions=retro.Actions.FILTERED,
            render_mode="rgb_array",
            inttype=retro.data.Integrations.ALL,
        )
        raw_obs, raw_info = self._env.reset()
        return self._translate_obs(raw_obs), self._translate_info(raw_info)

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
    # Format translation
    # ------------------------------------------------------------------

    def _translate_obs(self, raw_obs: np.ndarray) -> dict[str, np.ndarray]:
        """Resize frame to obs_size x obs_size; serve as both P1 and P2."""
        resized = cv2.resize(raw_obs, (self._obs_size, self._obs_size))
        return {"P1": resized, "P2": resized}

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
        return np.concatenate([action_dict["P1"], action_dict["P2"]])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_rom(self, retro) -> None:
        """Download ROM from S3 into stable-retro's data dir if not present.

        Uses sync boto3 (not async aioboto3) because this runs inside an
        already-running asyncio event loop from celery_async_run().
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
