"""Shared test fixtures for integration tests.

Uses an in-memory SQLite database via aiosqlite for isolation
(no external DB needed). External services (Redis, Solana, Celery)
are mocked. PostgreSQL-specific UUID columns are compiled as
VARCHAR(36) on SQLite via a type compiler patch.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rawl.config import settings
from rawl.db.base import Base

# Import all models so metadata is populated
from rawl.db.models.bet import Bet
from rawl.db.models.calibration_match import CalibrationMatch
from rawl.db.models.failed_upload import FailedUpload
from rawl.db.models.fighter import Fighter
from rawl.db.models.match import Match
from rawl.db.models.training_job import TrainingJob
from rawl.db.models.user import User
from rawl.gateway.auth import derive_api_key, hash_api_key

# ---------------------------------------------------------------------------
# SQLite UUID compat — teach SQLite to compile PG UUID as VARCHAR(36)
# ---------------------------------------------------------------------------
import sqlalchemy.dialects.sqlite.base as _sqlite_base

if not hasattr(_sqlite_base.SQLiteTypeCompiler, "visit_UUID"):
    def _visit_uuid(self, type_, **kw):
        return "VARCHAR(36)"
    _sqlite_base.SQLiteTypeCompiler.visit_UUID = _visit_uuid

# ---------------------------------------------------------------------------
# Database — in-memory SQLite via aiosqlite
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite://"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

_tables_created = False


@pytest.fixture
async def db_session():
    """Per-test session with rollback for isolation."""
    global _tables_created
    if not _tables_created:
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _tables_created = True

    conn = await _test_engine.connect()
    txn = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)

    yield session

    await session.close()
    await txn.rollback()
    await conn.close()


# ---------------------------------------------------------------------------
# Mock external services
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_redis():
    """Replace redis_pool with an in-memory mock for all tests."""
    store: dict[str, bytes | str | int] = {}
    ttls: dict[str, int] = {}
    sorted_sets: dict[str, dict[str, float]] = {}

    mock = MagicMock()

    async def _get(key):
        return store.get(key)

    async def _set(key, value, **kwargs):
        store[key] = value
        if "ex" in kwargs:
            ttls[key] = kwargs["ex"]

    async def _incr(key):
        val = int(store.get(key, 0)) + 1
        store[key] = val
        return val

    async def _expire(key, seconds):
        ttls[key] = seconds

    async def _ttl(key):
        return ttls.get(key, -1)

    async def _delete(*keys):
        for k in keys:
            store.pop(k, None)

    async def _ping():
        return True

    async def _scan(cursor=0, match=None, count=None):
        all_keys = list(store.keys()) + list(sorted_sets.keys())
        if match:
            import fnmatch
            all_keys = [k for k in all_keys if fnmatch.fnmatch(k, match)]
        return (0, all_keys)

    async def _zadd(key, mapping, **kwargs):
        if key not in sorted_sets:
            sorted_sets[key] = {}
        sorted_sets[key].update(mapping)

    async def _zrange(key, start, end, withscores=False, **kwargs):
        ss = sorted_sets.get(key, {})
        items = sorted(ss.items(), key=lambda x: x[1])
        if end == -1:
            items = items[start:]
        else:
            items = items[start : end + 1]
        if withscores:
            return items
        return [m for m, _ in items]

    async def _zrangebyscore(key, min_s, max_s, withscores=False, **kwargs):
        ss = sorted_sets.get(key, {})
        items = [
            (m, s)
            for m, s in sorted(ss.items(), key=lambda x: x[1])
            if min_s <= s <= max_s
        ]
        if withscores:
            return items
        return [m for m, _ in items]

    async def _zrem(key, *members):
        ss = sorted_sets.get(key, {})
        for m in members:
            ss.pop(m, None)

    def _pipeline():
        pipe = MagicMock()
        _pipe_ops = []

        def _pipe_zadd(key, mapping, **kwargs):
            _pipe_ops.append(("zadd", key, mapping))

        def _pipe_set(key, value, **kwargs):
            _pipe_ops.append(("set", key, value, kwargs))

        def _pipe_zrem(key, *members):
            _pipe_ops.append(("zrem", key, members))

        def _pipe_delete(*keys):
            _pipe_ops.append(("delete", keys))

        async def _pipe_execute():
            for op in _pipe_ops:
                if op[0] == "zadd":
                    await _zadd(op[1], op[2])
                elif op[0] == "set":
                    await _set(op[1], op[2], **op[3])
                elif op[0] == "zrem":
                    await _zrem(op[1], *op[2])
                elif op[0] == "delete":
                    await _delete(*op[1])
            _pipe_ops.clear()

        pipe.zadd = _pipe_zadd
        pipe.set = _pipe_set
        pipe.zrem = _pipe_zrem
        pipe.delete = _pipe_delete
        pipe.execute = _pipe_execute
        return pipe

    mock.get = _get
    mock.set = _set
    mock.incr = _incr
    mock.expire = _expire
    mock.ttl = _ttl
    mock.delete = _delete
    mock.ping = _ping
    mock.scan = _scan
    mock.zadd = _zadd
    mock.zrange = _zrange
    mock.zrangebyscore = _zrangebyscore
    mock.zrem = _zrem
    mock.pipeline = _pipeline
    async def _rate_limit_check(key: str, limit: int, window_seconds: int) -> bool:
        val = int(store.get(key, 0)) + 1
        store[key] = val
        if val == 1:
            ttls[key] = window_seconds
        return val <= limit

    async def _atomic_pair_remove(key: str, member_a: str, member_b: str) -> bool:
        ss = sorted_sets.get(key, {})
        if member_a in ss and member_b in ss:
            ss.pop(member_a)
            ss.pop(member_b)
            return True
        return False

    mock.rate_limit_check = _rate_limit_check
    mock.atomic_pair_remove = _atomic_pair_remove
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()

    with patch("rawl.redis_client.redis_pool", mock), \
         patch("rawl.api.middleware.redis_pool", mock), \
         patch("rawl.gateway.routes.submit.redis_pool", mock), \
         patch("rawl.services.match_queue.redis_pool", mock):
        yield mock


@pytest.fixture(autouse=True)
def mock_evm():
    """Replace EVM client with AsyncMock."""
    mock = AsyncMock()
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()
    mock.get_health = AsyncMock(return_value=True)
    mock.create_match_on_chain = AsyncMock(return_value="0xfake_tx_hash")
    with patch("rawl.evm.client.evm_client", mock):
        yield mock


# ---------------------------------------------------------------------------
# FastAPI app + httpx client
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _noop_lifespan(app):
    yield


@pytest.fixture
async def app(db_session):
    """FastAPI app with overridden DB dependency and no lifespan."""
    from rawl.dependencies import get_db
    from rawl.main import create_app

    application = create_app()
    application.router.lifespan_context = _noop_lifespan
    application.state.arq_pool = AsyncMock()

    async def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    """httpx AsyncClient for making requests against the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def make_internal_token(expired: bool = False) -> str:
    """Create an internal JWT token for testing."""
    now = int(time.time())
    payload = {
        "iss": "rawl-frontend",
        "iat": now,
        "exp": now + (-10 if expired else 300),
    }
    return jwt.encode(payload, settings.internal_jwt_secret, algorithm="HS256")


@pytest.fixture
def internal_token_header() -> dict[str, str]:
    return {"X-Internal-Token": make_internal_token()}


@pytest.fixture
def expired_token_header() -> dict[str, str]:
    return {"X-Internal-Token": make_internal_token(expired=True)}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

@pytest.fixture
async def seed_user(db_session) -> User:
    """Create a single test user with API key."""
    wallet = "0x1111111111111111111111111111111111111111"
    api_key = derive_api_key(wallet)
    user = User(
        wallet_address=wallet,
        api_key_hash=hash_api_key(api_key),
    )
    db_session.add(user)
    await db_session.flush()
    user._test_api_key = api_key
    return user


@pytest.fixture
async def seed_user_b(db_session) -> User:
    """Create a second test user."""
    wallet = "0x2222222222222222222222222222222222222222"
    api_key = derive_api_key(wallet)
    user = User(
        wallet_address=wallet,
        api_key_hash=hash_api_key(api_key),
    )
    db_session.add(user)
    await db_session.flush()
    user._test_api_key = api_key
    return user


@pytest.fixture
async def seed_fighters(db_session, seed_user, seed_user_b) -> list[Fighter]:
    """Create fighters in various statuses."""
    fighters = [
        Fighter(
            owner_id=seed_user.id, name="ReadyBot", game_id="sf2ce",
            character="Ryu", model_path="models/ready.zip",
            status="ready", elo_rating=1400.0, wins=10, losses=5,
            matches_played=15,
        ),
        Fighter(
            owner_id=seed_user.id, name="ValidatingBot", game_id="sf2ce",
            character="Ken", model_path="models/validating.zip",
            status="validating", elo_rating=1200.0,
        ),
        Fighter(
            owner_id=seed_user_b.id, name="OpponentBot", game_id="sf2ce",
            character="Guile", model_path="models/opponent.zip",
            status="ready", elo_rating=1300.0, wins=8, losses=7,
            matches_played=15,
        ),
        Fighter(
            owner_id=seed_user_b.id, name="OtherGameBot", game_id="kof98",
            character="Kyo", model_path="models/kof.zip",
            status="ready", elo_rating=1100.0,
        ),
    ]
    for f in fighters:
        db_session.add(f)
    await db_session.flush()
    return fighters


@pytest.fixture
async def seed_matches(db_session, seed_fighters) -> list[Match]:
    """Create matches in various statuses."""
    fa, _fv, fb, _fk = seed_fighters
    matches = [
        Match(
            game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
            fighter_b_id=fb.id, status="open", match_type="ranked",
        ),
        Match(
            game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
            fighter_b_id=fb.id, status="locked", match_type="ranked",
        ),
        Match(
            game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
            fighter_b_id=fb.id, status="resolved", match_type="ranked",
            winner_id=fa.id, side_a_total=5.0, side_b_total=3.0,
        ),
    ]
    for m in matches:
        db_session.add(m)
    await db_session.flush()
    return matches


@pytest.fixture
async def seed_bets(db_session, seed_matches) -> list[Bet]:
    """Create bets for testing."""
    open_match = seed_matches[0]
    bets = [
        Bet(
            match_id=open_match.id,
            wallet_address="0xAAAAAAAAA1000000000000000000000000000000",
            side="a", amount_eth=2.0, status="confirmed",
        ),
        Bet(
            match_id=open_match.id,
            wallet_address="0xBBBBBBBBB1000000000000000000000000000000",
            side="b", amount_eth=3.0, status="confirmed",
        ),
    ]
    for b in bets:
        db_session.add(b)
    await db_session.flush()
    return bets


@pytest.fixture
def api_key_header(seed_user) -> dict[str, str]:
    """Return X-Api-Key header for the first test user."""
    return {"X-Api-Key": seed_user._test_api_key}


@pytest.fixture
def api_key_header_b(seed_user_b) -> dict[str, str]:
    """Return X-Api-Key header for the second test user."""
    return {"X-Api-Key": seed_user_b._test_api_key}
