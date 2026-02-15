from __future__ import annotations

from fastapi import APIRouter

from rawl.gateway.routes import register, submit, training, match, fighters, leaderboard

gateway_router = APIRouter()

gateway_router.include_router(register.router)
gateway_router.include_router(submit.router)
gateway_router.include_router(training.router)
gateway_router.include_router(match.router)
gateway_router.include_router(fighters.router)
gateway_router.include_router(leaderboard.router)
