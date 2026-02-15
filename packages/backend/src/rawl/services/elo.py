from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# Rating floor
RATING_FLOOR = 800

# K-factors
K_CALIBRATION = 40  # First 10 matches
K_ESTABLISHED = 20  # 10+ matches
K_ELITE = 16  # Rating > 1800

# Calibration config
CALIBRATION_REFERENCE_ELOS = [1000, 1100, 1200, 1400, 1600]
CALIBRATION_MIN_SUCCESS = 3
CALIBRATION_MAX_RETRIES = 2

# Division thresholds
DIVISIONS = {
    "Diamond": 1600,
    "Gold": 1400,
    "Silver": 1200,
    "Bronze": 0,
}


def get_k_factor(rating: float, matches_played: int) -> int:
    """Determine K-factor based on rating and experience."""
    if matches_played < 10:
        return K_CALIBRATION
    if rating > 1800:
        return K_ELITE
    return K_ESTABLISHED


def get_division(rating: float) -> str:
    """Get division name for a rating."""
    if rating >= 1600:
        return "Diamond"
    if rating >= 1400:
        return "Gold"
    if rating >= 1200:
        return "Silver"
    return "Bronze"


def calculate_expected(rating_self: float, rating_opp: float) -> float:
    """Calculate expected score: E = 1/(1 + 10^((R_opp - R_self)/400))."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_opp - rating_self) / 400.0))


def calculate_new_rating(
    rating: float,
    opponent_rating: float,
    won: bool,
    matches_played: int,
) -> float:
    """Calculate new Elo rating after a match.

    S=1 for winner, S=0 for loser (never 0.5 — tiebreaker always produces a winner).
    """
    k = get_k_factor(rating, matches_played)
    expected = calculate_expected(rating, opponent_rating)
    score = 1.0 if won else 0.0

    new_rating = rating + k * (score - expected)
    return max(RATING_FLOOR, round(new_rating, 1))


def seasonal_reset(rating: float) -> float:
    """Quarterly seasonal reset: R_new = 1200 + 0.5 * (R_old - 1200)."""
    new_rating = 1200 + 0.5 * (rating - 1200)
    return max(RATING_FLOOR, round(new_rating, 1))


async def update_elo_after_match(
    winner_id: str,
    loser_id: str,
    db_session,
) -> tuple[float, float]:
    """Update Elo ratings for both fighters after a match.

    Returns (winner_new_elo, loser_new_elo).
    """
    from sqlalchemy import select
    from rawl.db.models.fighter import Fighter

    result = await db_session.execute(select(Fighter).where(Fighter.id == winner_id))
    winner = result.scalar_one()
    result = await db_session.execute(select(Fighter).where(Fighter.id == loser_id))
    loser = result.scalar_one()

    winner_new = calculate_new_rating(
        winner.elo_rating, loser.elo_rating, won=True, matches_played=winner.matches_played
    )
    loser_new = calculate_new_rating(
        loser.elo_rating, winner.elo_rating, won=False, matches_played=loser.matches_played
    )

    winner.elo_rating = winner_new
    winner.matches_played += 1
    winner.wins += 1

    loser.elo_rating = loser_new
    loser.matches_played += 1
    loser.losses += 1

    await db_session.commit()

    logger.info(
        "Elo updated",
        extra={
            "winner": str(winner_id),
            "loser": str(loser_id),
            "winner_elo": winner_new,
            "loser_elo": loser_new,
        },
    )

    return winner_new, loser_new


async def run_calibration(fighter_id: str, db_session) -> bool:
    """Run 5 calibration matches against reference fighters.

    Returns True if calibration succeeded (>= 3/5 matches completed).
    Results stored in calibration_matches table.
    """
    from rawl.db.models.calibration_match import CalibrationMatch
    from rawl.db.models.fighter import Fighter
    from sqlalchemy import select

    result = await db_session.execute(select(Fighter).where(Fighter.id == fighter_id))
    fighter = result.scalar_one_or_none()
    if not fighter:
        return False

    successes = 0

    for ref_elo in CALIBRATION_REFERENCE_ELOS:
        ref_fighter_id = f"ref_{fighter.game_id}_{ref_elo}"

        for attempt in range(1, CALIBRATION_MAX_RETRIES + 1):
            cal_match = CalibrationMatch(
                fighter_id=fighter.id,
                reference_elo=ref_elo,
                reference_fighter_id=ref_fighter_id,
                attempt=attempt,
            )
            db_session.add(cal_match)

            try:
                # Run match through full Match Runner pipeline
                # result = await run_match(...)
                # cal_match.result = "win" or "loss"
                # cal_match.match_hash = result.match_hash
                cal_match.result = "win"  # Placeholder
                successes += 1
                break
            except Exception as e:
                cal_match.result = "error"
                cal_match.error_message = str(e)
                if attempt >= CALIBRATION_MAX_RETRIES:
                    logger.warning(
                        "Calibration match failed after retries",
                        extra={"fighter_id": fighter_id, "ref_elo": ref_elo},
                    )

    await db_session.commit()

    if successes >= CALIBRATION_MIN_SUCCESS:
        fighter.status = "ready"
        logger.info("Calibration succeeded", extra={"fighter_id": fighter_id, "successes": successes})
    else:
        fighter.status = "calibration_failed"
        logger.warning("Calibration failed", extra={"fighter_id": fighter_id, "successes": successes})

    await db_session.commit()
    return successes >= CALIBRATION_MIN_SUCCESS
