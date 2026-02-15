from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Thresholds (at ~60fps)
CONSECUTIVE_THRESHOLD = 300  # ~5 seconds
TOTAL_THRESHOLD = 900  # ~15 seconds cumulative


@dataclass
class FieldCounter:
    consecutive_missing: int = 0
    total_missing: int = 0
    warned: bool = False  # Log warning once per field per match


@dataclass
class FieldValidator:
    """Continuous RAM field validation per SDD Section 5.3.5.

    Tracks consecutive and total missing frame counts for each required field.
    """

    match_id: str
    required_fields: list[str]
    _counters: dict[str, dict[str, FieldCounter]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for player in ("P1", "P2"):
            self._counters[player] = {f: FieldCounter() for f in self.required_fields}

    def check_frame(self, info: dict) -> list[str]:
        """Check a single frame's info dict for missing fields.

        Returns a list of error messages if any threshold is exceeded.
        Empty list means all fields are within tolerance.
        """
        errors = []

        for player in ("P1", "P2"):
            player_info = info.get(player, {})
            for field_name in self.required_fields:
                counter = self._counters[player][field_name]

                if field_name not in player_info:
                    counter.consecutive_missing += 1
                    counter.total_missing += 1

                    # Log warning once per field per match
                    if not counter.warned:
                        counter.warned = True
                        logger.warning(
                            "Required field missing",
                            extra={
                                "match_id": self.match_id,
                                "player": player,
                                "field": field_name,
                            },
                        )

                    # Check thresholds
                    if counter.consecutive_missing >= CONSECUTIVE_THRESHOLD:
                        errors.append(
                            f"{player}.{field_name}: {counter.consecutive_missing} consecutive "
                            f"missing frames (threshold: {CONSECUTIVE_THRESHOLD})"
                        )
                    if counter.total_missing >= TOTAL_THRESHOLD:
                        errors.append(
                            f"{player}.{field_name}: {counter.total_missing} total "
                            f"missing frames (threshold: {TOTAL_THRESHOLD})"
                        )
                else:
                    # Field present — reset consecutive counter
                    counter.consecutive_missing = 0

        return errors

    def has_errors(self, info: dict) -> bool:
        """Convenience: returns True if any threshold exceeded."""
        return len(self.check_frame(info)) > 0

    def get_status(self) -> dict[str, dict[str, dict[str, int]]]:
        """Return current counter state for debugging."""
        result = {}
        for player, fields in self._counters.items():
            result[player] = {}
            for field_name, counter in fields.items():
                result[player][field_name] = {
                    "consecutive_missing": counter.consecutive_missing,
                    "total_missing": counter.total_missing,
                }
        return result
