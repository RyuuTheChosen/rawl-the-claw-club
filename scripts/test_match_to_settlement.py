#!/usr/bin/env python3
"""End-to-end integration test: real emulated match -> on-chain settlement.

Runs a real SF2 match in WSL2 via stable-retro, then settles the result
on the Solana localnet with full betting flow.

Flow:
  1. Create match on-chain (MatchPool + Vault)
  2. Place bets from two test wallets
  3. Lock match on-chain
  4. Run real SF2 match in WSL2 (random actions, headless)
  5. Resolve match on-chain with the real winner
  6. Claim payout for winning bettor
  7. Verify balances and payout math

Usage:
    python scripts/test_match_to_settlement.py

Prerequisites:
    - Solana test validator running (localhost:8899)
    - Contract deployed + PlatformConfig initialized
    - WSL2 (Ubuntu-22.04) with stable-retro installed
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "backend" / "src"))

DIVIDER = "=" * 64
SEPARATOR = "-" * 64


def run_emulation(match_format: int = 3) -> dict:
    """Run a real SF2 match in WSL2 and return the result."""
    script_path = "/mnt/c/Projects/Rawl/scripts/run_match_headless.py"
    cmd = [
        "wsl", "-d", "Ubuntu-22.04", "--",
        "bash", "-lc",
        f"SDL_VIDEODRIVER=dummy python3 {script_path} --format {match_format}",
    ]
    print(f"  Launching WSL2 emulation (Bo{match_format})...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    # stderr has progress logs
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            print(f"  [EMU] {line}")

    if result.returncode != 0:
        print(f"  [ERROR] Emulation failed (exit code {result.returncode})")
        if result.stderr:
            print(f"  stderr: {result.stderr[-500:]}")
        sys.exit(1)

    # stdout has the JSON result (last line)
    stdout_lines = result.stdout.strip().split("\n")
    return json.loads(stdout_lines[-1])


async def main():
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    from solders.keypair import Keypair
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

    # Generate test wallets
    bettor_a = Keypair()
    bettor_b = Keypair()

    print(DIVIDER)
    print("  MATCH-TO-SETTLEMENT INTEGRATION TEST")
    print(DIVIDER)
    print(f"  Oracle:   {oracle_pk}")
    print(f"  Bettor A: {bettor_a.pubkey()}")
    print(f"  Bettor B: {bettor_b.pubkey()}")

    # Airdrop SOL
    print(f"\n{SEPARATOR}")
    print("  Phase 1: Fund test wallets")
    print(f"{SEPARATOR}")
    for label, kp in [("Oracle", oracle_kp), ("Bettor A", bettor_a), ("Bettor B", bettor_b)]:
        resp = await client.request_airdrop(kp.pubkey(), 10_000_000_000)
        await client.confirm_transaction(resp.value, commitment=Confirmed)
    await asyncio.sleep(2)
    for label, kp in [("Oracle", oracle_kp), ("Bettor A", bettor_a), ("Bettor B", bettor_b)]:
        bal = await client.get_balance(kp.pubkey(), commitment=Confirmed)
        print(f"  {label}: {bal.value / 1e9:.2f} SOL")

    # Transaction helper
    async def send_tx(ix, signers, label):
        from solana.rpc.types import TxOpts

        resp = await client.get_latest_blockhash()
        blockhash = resp.value.blockhash
        tx = SoldersTransaction.new_signed_with_payer(
            [ix], signers[0].pubkey(), signers, blockhash,
        )
        result = await client.send_transaction(
            tx, opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
        )
        sig = result.value
        await client.confirm_transaction(sig, commitment=Confirmed)

        # Check for errors
        tx_resp = await client.get_transaction(sig, commitment=Confirmed)
        if tx_resp.value and tx_resp.value.transaction.meta:
            meta = tx_resp.value.transaction.meta
            if meta.err:
                print(f"  [{label}] FAILED: {meta.err}")
                if meta.log_messages:
                    for log in meta.log_messages:
                        print(f"    LOG: {log}")
                return str(sig), False

        print(f"  [{label}] OK  tx: {str(sig)[:24]}...")
        return str(sig), True

    match_id = str(uuid.uuid4())
    match_format = 3

    # Phase 2: Create match on-chain
    print(f"\n{SEPARATOR}")
    print(f"  Phase 2: Create match pool (ID: {match_id[:8]}...)")
    print(f"{SEPARATOR}")
    create_ix = build_create_match_ix(
        match_id, bettor_a.pubkey(), bettor_b.pubkey(), oracle_pk
    )
    _, ok = await send_tx(create_ix, [oracle_kp], "create_match")
    if not ok:
        return

    pool_pda, _ = derive_match_pool_pda(match_id)
    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  MatchPool PDA: {pool_pda}")
    print(f"  Status: Open={pool.status == 0}")

    # Phase 3: Place bets
    print(f"\n{SEPARATOR}")
    print("  Phase 3: Place bets")
    print(f"{SEPARATOR}")
    bet_a_amount = 2_000_000_000   # 2 SOL on side A (P1)
    bet_b_amount = 1_000_000_000   # 1 SOL on side B (P2)

    place_a_ix = build_place_bet_ix(match_id, bettor_a.pubkey(), 0, bet_a_amount)
    await send_tx(place_a_ix, [bettor_a], "bet A  2 SOL -> Side A (P1)")

    place_b_ix = build_place_bet_ix(match_id, bettor_b.pubkey(), 1, bet_b_amount)
    await send_tx(place_b_ix, [bettor_b], "bet B  1 SOL -> Side B (P2)")

    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  Pool: Side A = {pool.side_a_total / 1e9:.2f} SOL, "
          f"Side B = {pool.side_b_total / 1e9:.2f} SOL, "
          f"Bets = {pool.bet_count}")

    # Phase 4: Lock match
    print(f"\n{SEPARATOR}")
    print("  Phase 4: Lock match (no more bets)")
    print(f"{SEPARATOR}")
    lock_ix = build_lock_match_ix(match_id, oracle_pk)
    await send_tx(lock_ix, [oracle_kp], "lock_match")

    # Phase 5: Run real match
    print(f"\n{SEPARATOR}")
    print("  Phase 5: Run real SF2 match (WSL2 emulation)")
    print(f"{SEPARATOR}")
    match_result = run_emulation(match_format)
    winner = match_result.get("winner")
    rounds = match_result.get("round_history", [])
    frames = match_result.get("frame_count", 0)

    if not winner:
        print(f"  [ERROR] No winner determined: {match_result.get('error', 'unknown')}")
        return

    print(f"\n  WINNER: {winner} in {frames} frames ({len(rounds)} rounds)")
    for i, r in enumerate(rounds, 1):
        print(f"    Round {i}: {r['winner']} wins "
              f"(P1 HP: {r['p1_health']:.0%}, P2 HP: {r['p2_health']:.0%})")

    # Phase 6: Resolve match on-chain
    print(f"\n{SEPARATOR}")
    print(f"  Phase 6: Resolve match on-chain (winner = {winner})")
    print(f"{SEPARATOR}")
    winner_code = 0 if winner == "P1" else 1
    resolve_ix = build_resolve_match_ix(match_id, oracle_pk, winner_code)
    await send_tx(resolve_ix, [oracle_kp], f"resolve ({winner} = Side {'A' if winner == 'P1' else 'B'})")

    resp = await client.get_account_info(pool_pda, commitment=Confirmed)
    pool = deserialize_match_pool(resp.value.data)
    print(f"  Status: Resolved={pool.status == 2}, Winner: Side{'A' if pool.winner == 1 else 'B'}={pool.winner}")

    # Phase 7: Claim payout
    print(f"\n{SEPARATOR}")
    print("  Phase 7: Claim payout")
    print(f"{SEPARATOR}")

    # Determine winning bettor
    winning_bettor = bettor_a if winner == "P1" else bettor_b
    losing_bettor = bettor_b if winner == "P1" else bettor_a
    winning_side = "A" if winner == "P1" else "B"

    vault_pda, _ = derive_vault_pda(match_id)
    bal_before = (await client.get_balance(winning_bettor.pubkey(), commitment=Confirmed)).value
    vault_before = (await client.get_balance(vault_pda, commitment=Confirmed)).value

    print(f"  Winning bettor (Side {winning_side}): {winning_bettor.pubkey()}")
    print(f"  Balance before claim: {bal_before / 1e9:.4f} SOL")
    print(f"  Vault before claim:   {vault_before / 1e9:.4f} SOL")

    claim_ix = build_claim_payout_ix(match_id, winning_bettor.pubkey())
    await send_tx(claim_ix, [winning_bettor], "claim_payout")

    bal_after = (await client.get_balance(winning_bettor.pubkey(), commitment=Confirmed)).value
    vault_after = (await client.get_balance(vault_pda, commitment=Confirmed)).value
    payout = bal_after - bal_before

    print(f"  Balance after claim:  {bal_after / 1e9:.4f} SOL")
    print(f"  Vault after claim:    {vault_after / 1e9:.4f} SOL")
    print(f"  Payout received:      {payout / 1e9:.4f} SOL")

    # Phase 8: Verify
    print(f"\n{SEPARATOR}")
    print("  Phase 8: Verification")
    print(f"{SEPARATOR}")

    total_pool = (bet_a_amount + bet_b_amount) / 1e9
    fee_bps = 300
    fee = total_pool * fee_bps / 10000
    net_pool = total_pool - fee
    expected_payout = net_pool  # Only one winner per side

    print(f"  Total pool:      {total_pool:.4f} SOL")
    print(f"  Platform fee:    {fee:.4f} SOL ({fee_bps} bps)")
    print(f"  Net pool:        {net_pool:.4f} SOL")
    print(f"  Expected payout: {expected_payout:.4f} SOL")
    print(f"  Actual payout:   {payout / 1e9:.4f} SOL")

    payout_match = abs(payout / 1e9 - expected_payout) < 0.01
    bet_pda, _ = derive_bet_pda(match_id, winning_bettor.pubkey())
    resp = await client.get_account_info(bet_pda, commitment=Confirmed)
    bet = deserialize_bet(resp.value.data)
    bet_claimed = bet.claimed

    print(f"\n  Bet claimed flag:  {bet_claimed}")
    print(f"  Payout correct:    {payout_match}")

    all_pass = payout_match and bet_claimed
    print(f"\n{DIVIDER}")
    print(f"  RESULT: {'ALL PASS' if all_pass else 'FAIL'}")
    print(f"  Match: {match_id}")
    print(f"  Winner: {winner} | Rounds: {len(rounds)} | Frames: {frames}")
    print(f"  Payout: {payout / 1e9:.4f} SOL (expected {expected_payout:.4f})")
    print(DIVIDER)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
