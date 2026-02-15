from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aioboto3

from rawl.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_session = aioboto3.Session()

RETRY_DELAYS = [30, 60, 120, 240, 480]


async def _get_client():
    return _session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


async def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    """Upload bytes to S3 with exponential backoff retry.

    Returns True on success. On total failure, returns False.
    """
    for attempt, delay in enumerate(RETRY_DELAYS):
        try:
            async with await _get_client() as client:
                await client.put_object(
                    Bucket=settings.s3_bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
            logger.info("S3 upload succeeded", extra={"key": key, "attempt": attempt + 1})
            return True
        except Exception:
            logger.warning(
                "S3 upload failed, retrying",
                extra={"key": key, "attempt": attempt + 1, "retry_delay": delay},
                exc_info=True,
            )
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)

    logger.error("S3 upload exhausted all retries", extra={"key": key})
    return False


async def download_bytes(key: str) -> bytes | None:
    """Download an object from S3. Returns None if not found."""
    try:
        async with await _get_client() as client:
            response = await client.get_object(Bucket=settings.s3_bucket, Key=key)
            return await response["Body"].read()
    except Exception:
        logger.error("S3 download failed", extra={"key": key}, exc_info=True)
        return None


async def ensure_bucket() -> None:
    """Create the bucket if it doesn't exist (for local dev with MinIO)."""
    try:
        async with await _get_client() as client:
            await client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        async with await _get_client() as client:
            await client.create_bucket(Bucket=settings.s3_bucket)
        logger.info("Created S3 bucket", extra={"bucket": settings.s3_bucket})
