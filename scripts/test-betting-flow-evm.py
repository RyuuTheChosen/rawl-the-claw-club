"""
End-to-end test of the full betting lifecycle on Base (Sepolia or local Anvil).

Usage:
  # Against local Anvil (anvil --fork-url ...):
  python scripts/test-betting-flow-evm.py --rpc http://127.0.0.1:8545

  # Against Base Sepolia:
  python scripts/test-betting-flow-evm.py --rpc https://sepolia.base.org

Required env vars:
  CONTRACT_ADDRESS   — Deployed RawlBetting contract
  ORACLE_PRIVATE_KEY — Private key for oracle account (has ORACLE_ROLE)
  ADMIN_PRIVATE_KEY  — Private key for admin account (has ADMIN_ROLE)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import uuid

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware


async def main(rpc_url: str) -> None:
    contract_address = os.environ["CONTRACT_ADDRESS"]
    oracle_key = os.environ["ORACLE_PRIVATE_KEY"]
    admin_key = os.environ.get("ADMIN_PRIVATE_KEY", oracle_key)

    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    oracle = Account.from_key(oracle_key)
    admin = Account.from_key(admin_key)

    # Minimal ABI for test
    abi = [
        {
            "type": "function",
            "name": "createMatch",
            "inputs": [
                {"name": "matchId", "type": "bytes32"},
                {"name": "fighterA", "type": "address"},
                {"name": "fighterB", "type": "address"},
                {"name": "minBet", "type": "uint128"},
                {"name": "bettingWindow", "type": "uint64"},
            ],
            "outputs": [],
            "stateMutability": "nonpayable",
        },
        {
            "type": "function",
            "name": "placeBet",
            "inputs": [
                {"name": "matchId", "type": "bytes32"},
                {"name": "side", "type": "uint8"},
            ],
            "outputs": [],
            "stateMutability": "payable",
        },
        {
            "type": "function",
            "name": "lockMatch",
            "inputs": [{"name": "matchId", "type": "bytes32"}],
            "outputs": [],
            "stateMutability": "nonpayable",
        },
        {
            "type": "function",
            "name": "resolveMatch",
            "inputs": [
                {"name": "matchId", "type": "bytes32"},
                {"name": "winner", "type": "uint8"},
            ],
            "outputs": [],
            "stateMutability": "nonpayable",
        },
        {
            "type": "function",
            "name": "claimPayout",
            "inputs": [{"name": "matchId", "type": "bytes32"}],
            "outputs": [],
            "stateMutability": "nonpayable",
        },
        {
            "type": "function",
            "name": "matches",
            "inputs": [{"name": "matchId", "type": "bytes32"}],
            "outputs": [
                {"name": "fighterA", "type": "address"},
                {"name": "fighterB", "type": "address"},
                {"name": "status", "type": "uint8"},
                {"name": "winner", "type": "uint8"},
                {"name": "sideABetCount", "type": "uint32"},
                {"name": "sideBBetCount", "type": "uint32"},
                {"name": "winningBetCount", "type": "uint32"},
                {"name": "betCount", "type": "uint32"},
                {"name": "feeBps", "type": "uint16"},
                {"name": "sideATotal", "type": "uint128"},
                {"name": "sideBTotal", "type": "uint128"},
                {"name": "createdAt", "type": "uint64"},
                {"name": "lockTimestamp", "type": "uint64"},
                {"name": "resolveTimestamp", "type": "uint64"},
                {"name": "cancelTimestamp", "type": "uint64"},
                {"name": "minBet", "type": "uint128"},
                {"name": "bettingWindow", "type": "uint64"},
                {"name": "feesWithdrawn", "type": "bool"},
            ],
            "stateMutability": "view",
        },
    ]

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Generate match ID
    match_uuid = uuid.uuid4()
    match_id_hex = match_uuid.hex
    match_id_bytes = bytes.fromhex(match_id_hex).ljust(32, b"\x00")
    print(f"Match UUID: {match_uuid}")
    print(f"Match bytes32: 0x{match_id_bytes.hex()}")

    fighter_a = oracle.address  # use oracle as fighter A for simplicity
    fighter_b = admin.address   # use admin as fighter B

    async def send_tx(fn_call, sender_key, value=0):
        sender = Account.from_key(sender_key)
        nonce = await w3.eth.get_transaction_count(sender.address, "pending")
        tx = await fn_call.build_transaction({
            "from": sender.address,
            "nonce": nonce,
            "chainId": await w3.eth.chain_id,
            "value": value,
        })
        tx["gas"] = await w3.eth.estimate_gas(tx)
        signed = sender.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt["status"] != 1:
            raise RuntimeError(f"TX reverted: {tx_hash.hex()}")
        return tx_hash.hex()

    # 1. Create match
    print("\n[1] Creating match...")
    tx = await send_tx(
        contract.functions.createMatch(
            match_id_bytes, fighter_a, fighter_b, w3.to_wei("0.001", "ether"), 0
        ),
        oracle_key,
    )
    print(f"    TX: {tx}")

    # Verify match state
    pool = await contract.functions.matches(match_id_bytes).call()
    assert pool[2] == 1, f"Expected status=1 (Open), got {pool[2]}"
    print("    Status: Open")

    # 2. Place bet (oracle bets on side A)
    print("\n[2] Placing bet (side A, 0.01 ETH)...")
    tx = await send_tx(
        contract.functions.placeBet(match_id_bytes, 0),
        oracle_key,
        value=w3.to_wei("0.01", "ether"),
    )
    print(f"    TX: {tx}")

    # 3. Place bet (admin bets on side B)
    print("\n[3] Placing bet (side B, 0.02 ETH)...")
    tx = await send_tx(
        contract.functions.placeBet(match_id_bytes, 1),
        admin_key,
        value=w3.to_wei("0.02", "ether"),
    )
    print(f"    TX: {tx}")

    # 4. Lock match
    print("\n[4] Locking match...")
    tx = await send_tx(contract.functions.lockMatch(match_id_bytes), oracle_key)
    print(f"    TX: {tx}")

    pool = await contract.functions.matches(match_id_bytes).call()
    assert pool[2] == 2, f"Expected status=2 (Locked), got {pool[2]}"
    print("    Status: Locked")

    # 5. Resolve match (side A wins = winner 0)
    print("\n[5] Resolving match (side A wins)...")
    tx = await send_tx(
        contract.functions.resolveMatch(match_id_bytes, 0), oracle_key
    )
    print(f"    TX: {tx}")

    pool = await contract.functions.matches(match_id_bytes).call()
    assert pool[2] == 3, f"Expected status=3 (Resolved), got {pool[2]}"
    print(f"    Status: Resolved, Winner: SideA")
    print(f"    Side A total: {w3.from_wei(pool[9], 'ether')} ETH")
    print(f"    Side B total: {w3.from_wei(pool[10], 'ether')} ETH")

    # 6. Claim payout (oracle = side A winner)
    balance_before = await w3.eth.get_balance(oracle.address)
    print(f"\n[6] Claiming payout...")
    tx = await send_tx(contract.functions.claimPayout(match_id_bytes), oracle_key)
    balance_after = await w3.eth.get_balance(oracle.address)
    payout = balance_after - balance_before
    print(f"    TX: {tx}")
    print(f"    Payout received: ~{w3.from_wei(payout, 'ether')} ETH (minus gas)")

    print("\n=== Full betting lifecycle verified! ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2E betting flow test on Base")
    parser.add_argument("--rpc", default="http://127.0.0.1:8545", help="RPC URL")
    args = parser.parse_args()
    asyncio.run(main(args.rpc))
