from __future__ import annotations

from rawl.game_adapters.base import GameAdapter, MatchState, TeamMatchState
from rawl.game_adapters.errors import AdapterValidationError, UnknownGameError
from rawl.game_adapters.sfiii3n import SFIII3NAdapter
from rawl.game_adapters.kof98 import KOF98Adapter
from rawl.game_adapters.tektagt import TekkenTagAdapter
from rawl.game_adapters.umk3 import UMK3Adapter
from rawl.game_adapters.doapp import DOAPPAdapter

_ADAPTER_REGISTRY: dict[str, type[GameAdapter]] = {
    "sfiii3n": SFIII3NAdapter,
    "kof98": KOF98Adapter,
    "tektagt": TekkenTagAdapter,
    "umk3": UMK3Adapter,
    "doapp": DOAPPAdapter,
}


def get_adapter(game_id: str) -> GameAdapter:
    """Get an adapter instance for the given game_id.

    Raises UnknownGameError if the game_id is not in the registry.
    """
    adapter_cls = _ADAPTER_REGISTRY.get(game_id)
    if adapter_cls is None:
        raise UnknownGameError(game_id, list(_ADAPTER_REGISTRY.keys()))
    return adapter_cls()


__all__ = [
    "GameAdapter",
    "MatchState",
    "TeamMatchState",
    "AdapterValidationError",
    "UnknownGameError",
    "get_adapter",
]
