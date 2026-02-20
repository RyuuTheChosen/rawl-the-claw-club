"""Unit tests for gateway auth utilities."""
from __future__ import annotations

import pytest

from rawl.gateway.auth import derive_api_key, hash_api_key


class TestDeriveApiKey:
    def test_deterministic(self):
        """Same wallet always produces the same key."""
        wallet = "TestWallet1111111111111111111111111111111111"
        k1 = derive_api_key(wallet)
        k2 = derive_api_key(wallet)
        assert k1 == k2

    def test_different_wallets_different_keys(self):
        k1 = derive_api_key("Wallet_A_11111111111111111111111111111111111")
        k2 = derive_api_key("Wallet_B_11111111111111111111111111111111111")
        assert k1 != k2

    def test_output_is_hex(self):
        key = derive_api_key("TestWallet1111111111111111111111111111111111")
        assert len(key) == 64
        int(key, 16)  # should not raise


class TestHashApiKey:
    def test_output_is_64_char_hex(self):
        h = hash_api_key("some_api_key_value")
        assert len(h) == 64
        int(h, 16)

    def test_deterministic(self):
        h1 = hash_api_key("same_key")
        h2 = hash_api_key("same_key")
        assert h1 == h2


class TestValidateApiKey:
    async def test_validate_api_key_success(self, client, seed_user, api_key_header):
        """Valid key returns 200 on a protected endpoint."""
        r = await client.get("/api/gateway/fighters", headers=api_key_header)
        assert r.status_code == 200

    async def test_validate_api_key_missing(self, client):
        r = await client.get("/api/gateway/fighters")
        assert r.status_code == 401

    async def test_validate_api_key_invalid(self, client):
        r = await client.get(
            "/api/gateway/fighters",
            headers={"X-Api-Key": "totally_invalid_key"},
        )
        assert r.status_code == 401
