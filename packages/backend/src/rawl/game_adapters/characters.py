"""Valid character registry per game.

Used by the submission API (input validation) and by RetroEngine
(safe state-file lookup).  Character names must exactly match the
.state file naming convention used by generate_sf2ce_states.py.
"""
from __future__ import annotations

import re

VALID_CHARACTERS: dict[str, list[str]] = {
    "sf2ce": [
        "Ryu", "Ken", "Honda", "ChunLi", "Blanka", "Guile",
        "Zangief", "Dhalsim", "Balrog", "Vega", "Sagat", "Bison",
    ],
    # Stubs — populated when integrations are added
    "sfiii3n": [],
    "kof98": [],
    "tektagt": [],
}

# Pre-compiled for fast validation (alphanumeric only, no path chars)
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9]+$")


def validate_character(game_id: str, character: str) -> bool:
    """Return True if *character* is in the allowlist for *game_id*.

    Returns False for unknown game_ids or empty allowlists (stubs).
    """
    chars = VALID_CHARACTERS.get(game_id)
    if not chars:
        return False
    return character in chars


def is_safe_character_name(name: str) -> bool:
    """Return True if *name* contains only alphanumeric characters.

    Defence-in-depth guard before using the name in filesystem paths.
    """
    return bool(_SAFE_NAME_RE.match(name))
