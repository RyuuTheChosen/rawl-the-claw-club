from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    match_id: str
    winner: str  # "P1" or "P2"
    round_history: list[dict]
    match_hash: str = ""
    adapter_version: str = ""
    hash_version: int = 2
    hash_payload: bytes = b""


def compute_match_hash(
    match_id: str,
    winner: str,
    round_history: list[dict],
    actions: list,
    adapter_version: str,
    hash_version: int = 2,
) -> tuple[bytes, str]:
    """Single-pass canonical JSON serialization for match hashing.

    Returns (hash_payload_bytes, hash_hex).
    The SAME bytes are hashed AND uploaded to S3.
    """
    payload_dict = {
        "actions": actions,
        "adapter_version": adapter_version,
        "hash_version": hash_version,
        "match_id": match_id,
        "rounds": round_history,
        "winner": winner,
    }
    # Canonical JSON: sorted keys, no whitespace
    payload_bytes = json.dumps(
        payload_dict, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    hash_hex = hashlib.sha256(payload_bytes).hexdigest()

    return payload_bytes, hash_hex


def resolve_tiebreaker(round_history: list[dict], match_id: str) -> str:
    """4-step tiebreaker cascade per SDD Section 5.7.

    1. Total health differential
    2. Total rounds won
    3. Last-round health
    4. SHA-256(match_id) mod 2 (deterministic coin flip)

    Always returns "P1" or "P2".
    """
    # Step 1: Total health differential
    p1_total_health = sum(r.get("p1_health", 0.0) for r in round_history)
    p2_total_health = sum(r.get("p2_health", 0.0) for r in round_history)

    if p1_total_health > p2_total_health:
        logger.info("Tiebreaker resolved by health differential", extra={"step": 1, "winner": "P1"})
        return "P1"
    if p2_total_health > p1_total_health:
        logger.info("Tiebreaker resolved by health differential", extra={"step": 1, "winner": "P2"})
        return "P2"

    # Step 2: Total rounds won
    p1_wins = sum(1 for r in round_history if r.get("winner") == "P1")
    p2_wins = sum(1 for r in round_history if r.get("winner") == "P2")

    if p1_wins > p2_wins:
        logger.info("Tiebreaker resolved by rounds won", extra={"step": 2, "winner": "P1"})
        return "P1"
    if p2_wins > p1_wins:
        logger.info("Tiebreaker resolved by rounds won", extra={"step": 2, "winner": "P2"})
        return "P2"

    # Step 3: Last-round health
    if round_history:
        last = round_history[-1]
        last_p1 = last.get("p1_health", 0.0)
        last_p2 = last.get("p2_health", 0.0)

        if last_p1 > last_p2:
            logger.info("Tiebreaker resolved by last-round health", extra={"step": 3, "winner": "P1"})
            return "P1"
        if last_p2 > last_p1:
            logger.info("Tiebreaker resolved by last-round health", extra={"step": 3, "winner": "P2"})
            return "P2"

    # Step 4: Deterministic coin flip
    coin = int(hashlib.sha256(match_id.encode()).hexdigest(), 16) % 2
    winner = "P1" if coin == 0 else "P2"
    logger.warning(
        "Tiebreaker resolved by deterministic coin flip",
        extra={"step": 4, "winner": winner, "match_id": match_id},
    )
    return winner
