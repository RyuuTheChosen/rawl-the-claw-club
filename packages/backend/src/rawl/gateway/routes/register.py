from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.gateway.auth import derive_api_key, hash_api_key, verify_wallet_signature
from rawl.gateway.schemas import RegisterRequest, RegisterResponse

router = APIRouter(tags=["gateway-auth"])


@router.post("/register", response_model=RegisterResponse)
async def register(db: DbSession, body: RegisterRequest):
    """Register a wallet and receive an API key.

    Requires a valid Ed25519 signature of the challenge message.
    """
    # Verify wallet signature
    if not verify_wallet_signature(body.wallet_address, body.signature, body.message):
        raise HTTPException(status_code=401, detail="Invalid wallet signature")

    # Check if already registered
    result = await db.execute(
        select(User).where(User.wallet_address == body.wallet_address)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.api_key_hash:
        raise HTTPException(status_code=409, detail="Wallet already registered")

    # Derive and store API key
    api_key = derive_api_key(body.wallet_address)
    key_hash = hash_api_key(api_key)

    if existing:
        existing.api_key_hash = key_hash
    else:
        user = User(
            wallet_address=body.wallet_address,
            api_key_hash=key_hash,
        )
        db.add(user)

    await db.commit()

    return RegisterResponse(api_key=api_key, wallet_address=body.wallet_address)
