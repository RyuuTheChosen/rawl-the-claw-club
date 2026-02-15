from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Header, Request
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from rawl.config import settings
from rawl.dependencies import DbSession

logger = logging.getLogger(__name__)


def derive_api_key(wallet_address: str) -> str:
    """Derive an API key using HMAC-SHA256(server_secret, wallet_address)."""
    return hmac.new(
        settings.internal_jwt_secret.encode(),
        wallet_address.encode(),
        hashlib.sha256,
    ).hexdigest()


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_wallet_signature(
    wallet_address: str,
    signature: str,
    message: str,
) -> bool:
    """Verify an Ed25519 wallet signature using PyNaCl.

    Used in challenge-response authentication flow.
    """
    try:
        from solders.pubkey import Pubkey
        import base58

        pubkey_bytes = bytes(Pubkey.from_string(wallet_address))
        verify_key = VerifyKey(pubkey_bytes)
        sig_bytes = base58.b58decode(signature)
        verify_key.verify(message.encode(), sig_bytes)
        return True
    except (BadSignatureError, Exception) as e:
        logger.warning(
            "Wallet signature verification failed",
            extra={"wallet": wallet_address, "error": str(e)},
        )
        return False


async def validate_api_key(
    request: Request,
    db: DbSession,
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency to validate API key and return wallet address."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-Api-Key header")

    key_hash = hash_api_key(x_api_key)

    from rawl.db.models.user import User
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.api_key_hash == key_hash))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return user.wallet_address


ApiKeyAuth = Annotated[str, Depends(validate_api_key)]
