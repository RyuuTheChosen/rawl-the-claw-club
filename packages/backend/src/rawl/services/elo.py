from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from rawl.config import settings

logger = logging.getLogger(__name__)

# Division thresholds (highest first for matching)
DIVISIONS = {
    "Diamond": 1600,
    "Gold": 1400,
    "Silver": 1200,
    "Bronze": 0,
}


def get_k_factor(rating: float, matches_played: int) -> int:
    """Determine K-factor based on rating and experience."""
    if matches_played < settings.elo_calibration_match_threshold:
        return settings.elo_k_calibration
    if rating > settings.elo_elite_threshold:
        return settings.elo_k_elite
    return settings.elo_k_established


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
    return max(settings.elo_rating_floor, round(new_rating, 1))


def seasonal_reset(rating: float) -> float:
    """Quarterly seasonal reset: R_new = 1200 + 0.5 * (R_old - 1200)."""
    new_rating = 1200 + 0.5 * (rating - 1200)
    return max(settings.elo_rating_floor, round(new_rating, 1))


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
    winner.division_tier = get_division(winner_new)

    loser.elo_rating = loser_new
    loser.matches_played += 1
    loser.losses += 1
    loser.division_tier = get_division(loser_new)

    await db_session.commit()

    logger.info(
        "Elo updated",
        extra={
            "winner": str(winner_id),
            "loser": str(loser_id),
            "winner_elo": winner_new,
            "loser_elo": loser_new,
            "winner_division": winner.division_tier,
            "loser_division": loser.division_tier,
        },
    )

    return winner_new, loser_new


async def run_calibration(fighter_id: str, db_session) -> bool:
    """Run calibration matches against reference fighters.

    Each calibration match runs the full match engine pipeline against a
    reference bot at the given Elo. The fighter's Elo is updated sequentially
    after each calibration match.

    Returns True if calibration succeeded (>= min_success matches completed).
    """
    from sqlalchemy import select

    from rawl.db.models.calibration_match import CalibrationMatch
    from rawl.db.models.fighter import Fighter
    from rawl.engine.match_runner import run_match

    result = await db_session.execute(select(Fighter).where(Fighter.id == fighter_id))
    fighter = result.scalar_one_or_none()
    if not fighter:
        return False

    reference_elos = settings.calibration_reference_elo_list
    successes = 0
    current_elo = fighter.elo_rating

    for ref_elo in reference_elos:
        ref_fighter_id = f"ref_{fighter.game_id}_{ref_elo}"

        for attempt in range(1, settings.calibration_max_retries + 1):
            cal_match = CalibrationMatch(
                fighter_id=fighter.id,
                reference_elo=ref_elo,
                reference_fighter_id=ref_fighter_id,
                attempt=attempt,
            )
            db_session.add(cal_match)

            try:
                match_result = await run_match(
                    match_id=f"cal_{fighter_id}_{ref_elo}_{attempt}",
                    game_id=fighter.game_id,
                    fighter_a_model_path=fighter.model_path,
                    fighter_b_model_path=f"reference/{fighter.game_id}/{ref_elo}",
                    match_format=settings.default_match_format,
                )

                if match_result is None:
                    raise RuntimeError("Match engine returned None")

                won = match_result.winner == "P1"
                cal_match.result = "win" if won else "loss"
                cal_match.match_hash = match_result.match_hash
                cal_match.round_history = str(match_result.round_history)

                # Sequential Elo update
                old_elo = current_elo
                current_elo = calculate_new_rating(
                    current_elo, float(ref_elo), won=won,
                    matches_played=fighter.matches_played + successes,
                )
                cal_match.elo_change = current_elo - old_elo
                cal_match.completed_at = datetime.now(UTC)

                successes += 1
                await db_session.flush()
                break  # success — move to next reference elo
            except Exception as e:
                cal_match.result = "error"
                cal_match.error_message = str(e)
                cal_match.completed_at = datetime.now(UTC)
                await db_session.flush()
                if attempt >= settings.calibration_max_retries:
                    logger.warning(
                        "Calibration match failed after retries",
                        extra={
                            "fighter_id": fighter_id,
                            "ref_elo": ref_elo,
                            "error": str(e),
                        },
                    )

    # Apply final Elo and update status
    fighter.elo_rating = current_elo
    fighter.division_tier = get_division(current_elo)

    if successes >= settings.calibration_min_success:
        fighter.status = "ready"
        logger.info(
            "Calibration succeeded",
            extra={
                "fighter_id": fighter_id,
                "successes": successes,
                "final_elo": current_elo,
            },
        )
    else:
        fighter.status = "calibration_failed"
        logger.warning(
            "Calibration failed",
            extra={
                "fighter_id": fighter_id,
                "successes": successes,
                "final_elo": current_elo,
            },
        )

    await db_session.commit()
    return successes >= settings.calibration_min_success
