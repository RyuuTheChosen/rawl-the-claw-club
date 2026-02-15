from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from rawl.config import Settings, settings
from rawl.db.session import async_session_factory


def get_settings() -> Settings:
    return settings


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
