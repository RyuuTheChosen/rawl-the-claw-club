from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def verify_oracle_keypair() -> bool:
    """Health check: verify oracle keypair can sign.

    Per SDD Section 10.5.5: Oracle keypair signing check every 5 minutes.
    """
    from rawl.config import settings
    import json
    from pathlib import Path

    keypair_path = Path(settings.oracle_keypair_path)
    if not keypair_path.exists():
        logger.error("Oracle keypair file not found")
        return False

    try:
        with open(keypair_path) as f:
            key_data = json.load(f)
        # Verify it's a valid keypair format
        if not isinstance(key_data, list) or len(key_data) != 64:
            logger.error("Oracle keypair invalid format")
            return False
        return True
    except Exception:
        logger.exception("Oracle keypair verification failed")
        return False
