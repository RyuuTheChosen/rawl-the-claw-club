"""Integration tests for rawl.services.anti_manipulation."""
from __future__ import annotations

import uuid

import pytest

from rawl.db.models.bet import Bet
from rawl.db.models.match import Match
from rawl.services.anti_manipulation import (
    audit_betting_patterns,
    check_betting_concentration,
    flag_cross_wallet_funding,
)

# EVM-format test wallets (0x + 40 hex chars — hex only: 0-9, a-f, A-F)
WHALE = "0xAA00AA0010000000000000000000000000000000"
SMALL = "0xBB00BB0010000000000000000000000000000000"
WALA = "0xCC00CCC000000000000000000000000000000000"
WALB = "0xDD00DDD000000000000000000000000000000000"
HIGHWIN = "0xEE00EEE100000000000000000000000000000000"
NORMAL = "0xFF00FFF100000000000000000000000000000000"


class TestBettingConcentration:
    async def test_concentration_alert(self, db_session, seed_fighters):
        """Single wallet >50% of a side + pool >10 ETH → alert."""
        fa, _, fb, _ = seed_fighters
        match = Match(
            game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
            fighter_b_id=fb.id, status="open",
            side_a_total=15.0, side_b_total=5.0,
        )
        db_session.add(match)
        await db_session.flush()

        bet = Bet(
            match_id=match.id, wallet_address=WHALE,
            side="a", amount_eth=12.0, status="confirmed",
        )
        db_session.add(bet)
        await db_session.flush()

        alerts = await check_betting_concentration(str(match.id), db_session)
        assert len(alerts) >= 1
        assert "concentration" in alerts[0].lower()

    async def test_concentration_no_alert_small_pool(self, db_session, seed_fighters):
        """Pool <10 ETH → no alert even if concentrated."""
        fa, _, fb, _ = seed_fighters
        match = Match(
            game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
            fighter_b_id=fb.id, status="open",
            side_a_total=5.0, side_b_total=2.0,
        )
        db_session.add(match)
        await db_session.flush()

        bet = Bet(
            match_id=match.id, wallet_address=SMALL,
            side="a", amount_eth=5.0, status="confirmed",
        )
        db_session.add(bet)
        await db_session.flush()

        alerts = await check_betting_concentration(str(match.id), db_session)
        assert len(alerts) == 0


class TestCrossWalletDetection:
    async def test_cross_wallet_detection(self, db_session, seed_fighters):
        """>=3 same-side overlaps → flagged."""
        fa, _, fb, _ = seed_fighters

        for _ in range(3):
            match = Match(
                game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
                fighter_b_id=fb.id, status="resolved",
            )
            db_session.add(match)
            await db_session.flush()

            db_session.add(Bet(
                match_id=match.id, wallet_address=WALA,
                side="a", amount_eth=1.0, status="confirmed",
            ))
            db_session.add(Bet(
                match_id=match.id, wallet_address=WALB,
                side="a", amount_eth=1.0, status="confirmed",
            ))
        await db_session.flush()

        flagged = await flag_cross_wallet_funding(WALA, db_session)
        assert flagged is True


class TestAuditBettingPatterns:
    async def test_audit_high_winrate(self, db_session, seed_fighters):
        """>80% win rate + >=10 bets → flagged."""
        fa, _, fb, _ = seed_fighters

        for i in range(10):
            match = Match(
                game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
                fighter_b_id=fb.id, status="resolved",
            )
            db_session.add(match)
            await db_session.flush()

            bet = Bet(
                match_id=match.id, wallet_address=HIGHWIN,
                side="a", amount_eth=1.0,
                status="claimed" if i < 9 else "confirmed",
            )
            db_session.add(bet)
        await db_session.flush()

        report = await audit_betting_patterns(HIGHWIN, db_session)
        assert report["flagged"] is True
        assert report["total_bets"] == 10
        assert report["winning_bets"] == 9

    async def test_audit_normal_pattern(self, db_session, seed_fighters):
        """50% win rate → not flagged."""
        fa, _, fb, _ = seed_fighters

        for i in range(10):
            match = Match(
                game_id="sf2ce", match_format=3, fighter_a_id=fa.id,
                fighter_b_id=fb.id, status="resolved",
            )
            db_session.add(match)
            await db_session.flush()

            bet = Bet(
                match_id=match.id, wallet_address=NORMAL,
                side="a", amount_eth=1.0,
                status="claimed" if i < 5 else "confirmed",
            )
            db_session.add(bet)
        await db_session.flush()

        report = await audit_betting_patterns(NORMAL, db_session)
        assert report["flagged"] is False
