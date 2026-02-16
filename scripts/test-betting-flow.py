#!/usr/bin/env python3
"""End-to-end betting flow test on local Solana validator.

Tests the complete cycle without DIAMBRA:
  1. Create match on-chain (MatchPool PDA)
  2. Place bets from two test wallets
  3. Lock match (oracle)
  4. Resolve match with winner (oracle)
  5. Claim payout (winning bettor)
  6. Verify balances

Usage:
    python scripts/test-betting-flow.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "backend" / "src"))


async def main():
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import ID as SYSTEM_PROGRAM_ID
    from solders.transaction import Transaction as SoldersTransaction

    from rawl.config import settings
    from rawl.solana.instructions import (
        build_create_match_ix,
        build_place_bet_ix,
        build_lock_match_ix,
        build_resolve_match_ix,
        build_claim_payout_ix,
    )
    from rawl.solana.pda import derive_match_pool_pda, derive_vault_pda, derive_bet_pda
    from rawl.solana.deserialize import deserialize_match_pool, deserialize_bet

    client = AsyncClient(settings.solana_rpc_url)

    # Load oracle keypair
    oracle_path = Path(settings.oracle_keypair_path)
    if not oracle_path.exists():
        print(f"[ERROR] Oracle keypair not found at {oracle_path}")
        return
    oracle_kp = Keypair.from_bytes(bytes(json.loads(oracle_path.read_text())))
    oracle_pk = oracle_kp.pubkey()
    print(f"Oracle:  {oracle_pk}")

    # Generate two test bettor wallets
    bettor_a = Keypair()
    bettor_b = Keypair()
    print(f"Bettor A: {bettor_a.pubkey()}")
    print(f"Bettor B: {bettor_b.pubkey()}")

    # Airdrop SOL to test wallets
    print("\n--- Airdropping SOL ---")
    for label, kp in [("Oracle", oracle_kp), ("Bettor A", bettor_a), ("Bettor B", bettor_b)]:
        resp = await client.request_airdrop(kp.pubkey(), 10_000_000_000)  # 10 SOL
        await client.confirm_transaction(resp.value, commitment=Confirmed)
    # Wait for all airdrops to be fully settled
    await asyncio.sleep(2)
    for label, kp in [("Oracle", oracle_kp), ("Bettor A", bettor_a), ("Bettor B", bettor_b)]:
        bal = await client.get_balance(kp.pubkey(), commitment=Confirmed)
        print(f"  {label} balance: {bal.value / 1e9:.2f} SOL")

    # Generate a match ID
    match_id = str(uuid.uuid4())
    print(f"\n--- Match ID: {match_id} ---")

    # Helper to build + send + confirm a transaction
    async def send_tx(ix, signers, label):
        from solana.rpc.types import TxOpts

        resp = await client.get_latest_blockhash()
        blockhash = resp.value.blockhash
        tx = SoldersTransaction.new_signed_with_payer(
            [ix],
            signers[0].pubkey(),
            signers,
            blockhash,
        )
        # Skip preflight to avoid simulation issues, confirm on-chain directly
        result = await client.send_transaction(
            tx, opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
        )
        sig = result.value
        await client.confirm_transaction(sig, commitment=Confirmed)

        # Check transaction status for errors
        tx_resp = await client.get_transaction(sig, commitment=Confirmed)
        if tx_resp.value and tx_resp.value.transaction.meta:
            meta = tx_resp.value.transaction.meta
            if meta.err:
                print(f"  [{label}] FAILED: {meta.err}")
                if meta.log_messages:
                    for log in meta.log_messages:
                        print(f"    LOG: {log}")
                return str(sig)

        print(f"  [{label}] tx: {sig}")
        return str(sig)

    # Step 1: Create match on-chain
    print("\n--- Step 1: Create match pool ---")
    create_ix = build_create_match_ix(
        match_id, bettor_a.pubkey(), bettor_b.pubkey(), oracle_pk
    )
    await send_tx(create_ix, [oracle_kp], "create_match")

    # Verify match pool PDA
    pool_pda, _ = derive_match_pool_pda(match_id)
    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  MatchPool PDA: {pool_pda}")
    print(f"  Status: Open={pool.status == 0}")

    # Step 2: Place bets
    print("\n--- Step 2: Place bets ---")
    bet_a_amount = 1_000_000_000  # 1 SOL on side A
    bet_b_amount = 500_000_000    # 0.5 SOL on side B

    place_a_ix = build_place_bet_ix(match_id, bettor_a.pubkey(), 0, bet_a_amount)
    await send_tx(place_a_ix, [bettor_a], "place_bet A (1 SOL, side A)")

    place_b_ix = build_place_bet_ix(match_id, bettor_b.pubkey(), 1, bet_b_amount)
    await send_tx(place_b_ix, [bettor_b], "place_bet B (0.5 SOL, side B)")

    # Verify pool state
    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  Side A total: {pool.side_a_total / 1e9:.2f} SOL")
    print(f"  Side B total: {pool.side_b_total / 1e9:.2f} SOL")
    print(f"  Bet count: {pool.bet_count}")

    # Verify bet PDAs
    bet_a_pda, _ = derive_bet_pda(match_id, bettor_a.pubkey())
    bet_b_pda, _ = derive_bet_pda(match_id, bettor_b.pubkey())
    resp_a = await client.get_account_info(bet_a_pda, commitment=Confirmed)
    resp_b = await client.get_account_info(bet_b_pda, commitment=Confirmed)
    bet_a = deserialize_bet(resp_a.value.data)
    bet_b = deserialize_bet(resp_b.value.data)
    print(f"  Bet A: side={bet_a.side}, amount={bet_a.amount / 1e9:.2f} SOL, claimed={bet_a.claimed}")
    print(f"  Bet B: side={bet_b.side}, amount={bet_b.amount / 1e9:.2f} SOL, claimed={bet_b.claimed}")

    # Step 3: Lock match
    print("\n--- Step 3: Lock match ---")
    lock_ix = build_lock_match_ix(match_id, oracle_pk)
    await send_tx(lock_ix, [oracle_kp], "lock_match")

    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  Status: Locked={pool.status == 1}")

    # Step 4: Resolve match (Side A wins)
    print("\n--- Step 4: Resolve match (Side A wins) ---")
    resolve_ix = build_resolve_match_ix(match_id, oracle_pk, 0)  # 0 = SideA wins
    await send_tx(resolve_ix, [oracle_kp], "resolve_match (winner=SideA)")

    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  Status: Resolved={pool.status == 2}")
    print(f"  Winner: SideA={pool.winner == 1}")

    # Record balances before claim
    bal_a_before = (await client.get_balance(bettor_a.pubkey(), commitment=Confirmed)).value
    bal_b_before = (await client.get_balance(bettor_b.pubkey(), commitment=Confirmed)).value
    vault_pda, _ = derive_vault_pda(match_id)
    vault_bal = (await client.get_balance(vault_pda, commitment=Confirmed)).value
    print(f"\n  Vault balance:    {vault_bal / 1e9:.4f} SOL")
    print(f"  Bettor A balance: {bal_a_before / 1e9:.4f} SOL")
    print(f"  Bettor B balance: {bal_b_before / 1e9:.4f} SOL")

    # Step 5: Claim payout (Bettor A wins)
    print("\n--- Step 5: Claim payout (Bettor A) ---")
    claim_ix = build_claim_payout_ix(match_id, bettor_a.pubkey())
    await send_tx(claim_ix, [bettor_a], "claim_payout")

    bal_a_after = (await client.get_balance(bettor_a.pubkey(), commitment=Confirmed)).value
    vault_after = (await client.get_balance(vault_pda, commitment=Confirmed)).value
    payout = bal_a_after - bal_a_before
    print(f"  Bettor A received: {payout / 1e9:.4f} SOL")
    print(f"  Vault remaining:   {vault_after / 1e9:.4f} SOL")

    # Verify bet marked as claimed
    resp_a = await client.get_account_info(bet_a_pda, commitment=Confirmed)
    bet_a = deserialize_bet(resp_a.value.data)
    print(f"  Bet A claimed: {bet_a.claimed}")

    # Summary
    total_pool = 1.5  # 1 + 0.5
    fee_bps = 300
    fee = total_pool * fee_bps / 10000
    net_pool = total_pool - fee
    expected_payout = net_pool  # Only winner on side A, so gets all of net pool
    print(f"\n--- Summary ---")
    print(f"  Total pool:     {total_pool:.2f} SOL")
    print(f"  Platform fee:   {fee:.4f} SOL ({fee_bps} bps)")
    print(f"  Net pool:       {net_pool:.4f} SOL")
    print(f"  Expected payout: {expected_payout:.4f} SOL")
    print(f"  Actual payout:   {payout / 1e9:.4f} SOL")
    print(f"  Match:  {'PASS' if abs(payout / 1e9 - expected_payout) < 0.01 else 'FAIL'}")

    await client.close()
    print("\nBetting flow test complete!")


if __name__ == "__main__":
    asyncio.run(main())
