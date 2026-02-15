from __future__ import annotations

from fastapi import APIRouter

from rawl.api.routes import fighters, leaderboard, matches, odds, internal

api_router = APIRouter()

api_router.include_router(matches.router)
api_router.include_router(fighters.router)
api_router.include_router(odds.router)
api_router.include_router(leaderboard.router)
api_router.include_router(internal.router)
