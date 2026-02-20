"""Integration tests for POST /api/gateway/register."""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestRegister:
    async def test_register_success(self, client):
        """Valid wallet signature → API key returned."""
        body = {
            "wallet_address": "NewWallet11111111111111111111111111111111111",
            "signature": "fake_sig_base58",
            "message": "Sign to authenticate",
        }
        with patch(
            "rawl.gateway.routes.register.verify_wallet_signature", return_value=True
        ):
            r = await client.post("/api/gateway/register", json=body)
        assert r.status_code == 200
        data = r.json()
        assert "api_key" in data
        assert data["wallet_address"] == body["wallet_address"]

    async def test_register_invalid_signature(self, client):
        body = {
            "wallet_address": "BadWallet11111111111111111111111111111111111",
            "signature": "bad_sig",
            "message": "Sign to authenticate",
        }
        with patch(
            "rawl.gateway.routes.register.verify_wallet_signature", return_value=False
        ):
            r = await client.post("/api/gateway/register", json=body)
        assert r.status_code == 401

    async def test_register_duplicate(self, client, seed_user):
        """Already-registered wallet → 409."""
        body = {
            "wallet_address": seed_user.wallet_address,
            "signature": "fake_sig",
            "message": "Sign to authenticate",
        }
        with patch(
            "rawl.gateway.routes.register.verify_wallet_signature", return_value=True
        ):
            r = await client.post("/api/gateway/register", json=body)
        assert r.status_code == 409
