from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class CursorParams(BaseModel):
    cursor: str | None = None
    limit: int = 20

    def decode_cursor(self) -> tuple[str, str] | None:
        """Decode cursor into (created_at_iso, match_uuid)."""
        if not self.cursor:
            return None
        try:
            decoded = base64.b64decode(self.cursor).decode()
            data = json.loads(decoded)
            return data["ts"], data["id"]
        except Exception:
            return None

    @staticmethod
    def encode_cursor(created_at: datetime, id_val: str) -> str:
        """Encode (created_at, id) into an opaque cursor string."""
        data = json.dumps({"ts": created_at.isoformat(), "id": str(id_val)})
        return base64.b64encode(data.encode()).decode()


class MatchFilterParams(BaseModel):
    status: str | None = None  # upcoming, live, completed, all
    game: str | None = None
    match_type: str | None = None  # ranked, challenge, exhibition, all
