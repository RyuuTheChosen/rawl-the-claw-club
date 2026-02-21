"""Unit tests for game_adapters.characters — character validation & safety."""
from __future__ import annotations

import pytest

from rawl.game_adapters.characters import (
    VALID_CHARACTERS,
    is_safe_character_name,
    validate_character,
)


class TestValidateCharacter:
    def test_valid_sf2ce_characters(self):
        for char in VALID_CHARACTERS["sf2ce"]:
            assert validate_character("sf2ce", char) is True

    def test_invalid_character_rejected(self):
        assert validate_character("sf2ce", "InvalidChar") is False

    def test_path_traversal_rejected(self):
        assert validate_character("sf2ce", "../../etc") is False

    def test_empty_string_rejected(self):
        assert validate_character("sf2ce", "") is False

    def test_unknown_game_rejected(self):
        assert validate_character("nonexistent_game", "Ryu") is False

    def test_stub_game_with_empty_list_rejected(self):
        # sfiii3n has an empty character list (stub)
        assert validate_character("sfiii3n", "Ryu") is False

    def test_case_sensitive(self):
        assert validate_character("sf2ce", "ryu") is False
        assert validate_character("sf2ce", "RYU") is False
        assert validate_character("sf2ce", "Ryu") is True


class TestIsSafeCharacterName:
    def test_alphanumeric_accepted(self):
        assert is_safe_character_name("Ryu") is True
        assert is_safe_character_name("ChunLi") is True
        assert is_safe_character_name("sf2ce") is True

    def test_path_separators_rejected(self):
        assert is_safe_character_name("../etc") is False
        assert is_safe_character_name("foo/bar") is False
        assert is_safe_character_name("foo\\bar") is False

    def test_dots_rejected(self):
        assert is_safe_character_name("file.state") is False
        assert is_safe_character_name("..") is False

    def test_spaces_rejected(self):
        assert is_safe_character_name("Chun Li") is False

    def test_empty_rejected(self):
        assert is_safe_character_name("") is False

    def test_special_chars_rejected(self):
        assert is_safe_character_name("Ryu;rm -rf") is False
        assert is_safe_character_name("Ryu$(cmd)") is False


class TestRegistryConsistency:
    def test_sf2ce_has_12_characters(self):
        assert len(VALID_CHARACTERS["sf2ce"]) == 12

    def test_all_sf2ce_names_are_safe(self):
        for char in VALID_CHARACTERS["sf2ce"]:
            assert is_safe_character_name(char), f"{char} is not safe"
