from __future__ import annotations


class AdapterValidationError(Exception):
    """Raised when required info fields are missing."""

    def __init__(self, game_id: str, missing_fields: dict[str, list[str]]) -> None:
        self.game_id = game_id
        self.missing_fields = missing_fields
        parts = []
        for player, fields in missing_fields.items():
            parts.append(f"{player}: {fields}")
        msg = f"Adapter validation failed for {game_id}. Missing fields — {'; '.join(parts)}"
        super().__init__(msg)


class UnknownGameError(Exception):
    """Raised when a game_id is not found in the adapter registry."""

    def __init__(self, game_id: str, available: list[str]) -> None:
        self.game_id = game_id
        self.available = available
        super().__init__(
            f"Unknown game_id '{game_id}'. Available: {available}"
        )
