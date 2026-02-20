from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from rawl.config import settings

# Main engine for FastAPI (long-lived, connection pooling)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Worker engine for subprocess workers (NullPool — no connection reuse across event loops).
# SQLAlchemy docs: "use NullPool for async engines used across multiple asyncio event loops".
# Each asyncio.run() in a subprocess gets fresh connections that don't persist.
worker_engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
)

worker_session_factory = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
