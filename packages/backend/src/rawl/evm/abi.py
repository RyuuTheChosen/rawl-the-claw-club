"""Load RawlBetting contract ABI from Foundry build artifact."""
from __future__ import annotations

import json
from pathlib import Path

_ABI_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "contracts"
    / "out"
    / "RawlBetting.sol"
    / "RawlBetting.json"
)


def load_abi() -> list:
    """Load ABI from Foundry artifact.

    Falls back to empty list if artifact not yet built (allows import during dev).
    """
    if _ABI_PATH.exists():
        return json.loads(_ABI_PATH.read_text())["abi"]
    return []


CONTRACT_ABI = load_abi()
