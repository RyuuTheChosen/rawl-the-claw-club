from __future__ import annotations

import logging

from sqlalchemy import select

from rawl.db.models.fighter import Fighter

logger = logging.getLogger(__name__)


async def get_fighter_model_path(fighter_id: str, db_session) -> str | None:
    """Look up a fighter's model S3 path from the registry."""
    result = await db_session.execute(
        select(Fighter.model_path).where(Fighter.id == fighter_id, Fighter.status == "ready")
    )
    return result.scalar_one_or_none()


async def update_fighter_status(fighter_id: str, status: str, db_session) -> None:
    """Update a fighter's status in the registry."""
    result = await db_session.execute(select(Fighter).where(Fighter.id == fighter_id))
    fighter = result.scalar_one_or_none()
    if fighter:
        fighter.status = status
        await db_session.commit()
        logger.info("Fighter status updated", extra={"fighter_id": fighter_id, "status": status})
