import pytest

from rawl.game_adapters import get_adapter, UnknownGameError
from rawl.game_adapters.sfiii3n import SFIII3NAdapter
from rawl.game_adapters.kof98 import KOF98Adapter
from rawl.game_adapters.tektagt import TekkenTagAdapter


def test_get_adapter_sfiii3n():
    adapter = get_adapter("sfiii3n")
    assert isinstance(adapter, SFIII3NAdapter)
    assert adapter.game_id == "sfiii3n"


def test_get_adapter_kof98():
    adapter = get_adapter("kof98")
    assert isinstance(adapter, KOF98Adapter)


def test_get_adapter_tektagt():
    adapter = get_adapter("tektagt")
    assert isinstance(adapter, TekkenTagAdapter)


def test_get_adapter_unknown():
    with pytest.raises(UnknownGameError) as exc_info:
        get_adapter("nonexistent")
    assert "nonexistent" in str(exc_info.value)
    assert "sfiii3n" in str(exc_info.value)


def test_stub_adapters_raise():
    for game_id in ("umk3", "doapp"):
        adapter = get_adapter(game_id)
        with pytest.raises(NotImplementedError):
            adapter.extract_state({})
