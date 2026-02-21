"""Load RawlBetting contract ABI from Foundry build artifact."""
from __future__ import annotations

import json
from pathlib import Path

# Bundled ABI (copied from Foundry out/ at build time — works in Docker / installed package)
_BUNDLED = Path(__file__).parent / "RawlBetting.json"

# Foundry output path (works in local dev monorepo)
_FOUNDRY = (
    Path(__file__).parent.parent.parent.parent.parent
    / "contracts"
    / "out"
    / "RawlBetting.sol"
    / "RawlBetting.json"
)


def load_abi() -> list:
    """Load ABI from bundled artifact, falling back to Foundry output for local dev."""
    for path in (_BUNDLED, _FOUNDRY):
        if path.exists():
            return json.loads(path.read_text())["abi"]
    return []


CONTRACT_ABI = load_abi()
