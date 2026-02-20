"""Integration tests for GET /api/bets and POST /api/matches/{id}/bets."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

# EVM-format test wallets (0x + 40 hex chars — hex only: 0-9, a-f, A-F)
WALLET_BET_A = "0xAAAAAAAAA1000000000000000000000000000000"
WALLET_BET_B = "0xBBBBBBBBB1000000000000000000000000000000"
WALLET_NEW = "0xCCCCCCCCC1000000000000000000000000000000"


class TestListBets:
    async def test_list_bets_by_wallet(self, client, seed_bets):
        r = await client.get("/api/bets", params={"wallet": WALLET_BET_A})
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["wallet_address"] == WALLET_BET_A

    async def test_list_bets_by_match(self, client, seed_bets, seed_matches):
        r = await client.get(
            "/api/bets",
            params={"wallet": WALLET_BET_A, "match_id": str(seed_matches[0].id)},
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_list_bets_empty(self, client):
        r = await client.get(
            "/api/bets",
            params={"wallet": "0x0000000000000000000000000000000000000000"},
        )
        assert r.status_code == 200
        assert r.json() == []


class TestRecordBet:
    async def test_record_bet_success(self, client, seed_matches):
        match_id = str(seed_matches[0].id)  # open match
        body = {
            "wallet_address": WALLET_NEW,
            "side": "a",
            "amount_eth": 1.5,
            "tx_hash": "0xfake_sig_abc123",
        }
        r = await client.post(f"/api/matches/{match_id}/bets", json=body)
        assert r.status_code == 201
        data = r.json()
        assert data["side"] == "a"
        assert data["amount_eth"] == 1.5
        assert data["status"] == "confirmed"

    async def test_record_bet_match_not_found(self, client):
        body = {
            "wallet_address": WALLET_NEW,
            "side": "a",
            "amount_eth": 1.0,
            "tx_hash": "0xfake_sig",
        }
        fake_id = str(uuid.uuid4())
        r = await client.post(f"/api/matches/{fake_id}/bets", json=body)
        assert r.status_code == 404

    async def test_record_bet_match_not_open(self, client, seed_matches):
        locked_match_id = str(seed_matches[1].id)  # locked match
        body = {
            "wallet_address": WALLET_NEW,
            "side": "b",
            "amount_eth": 1.0,
            "tx_hash": "0xfake_sig",
        }
        r = await client.post(f"/api/matches/{locked_match_id}/bets", json=body)
        assert r.status_code == 400

    async def test_record_bet_duplicate(self, client, seed_matches, seed_bets):
        match_id = str(seed_matches[0].id)
        body = {
            "wallet_address": WALLET_BET_A,
            "side": "a",
            "amount_eth": 1.0,
            "tx_hash": "0xfake_sig",
        }
        r = await client.post(f"/api/matches/{match_id}/bets", json=body)
        assert r.status_code == 409
