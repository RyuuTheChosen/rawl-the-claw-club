"""Initialize the Rawl PlatformConfig on-chain after contract deployment.

Usage:
    cd /c/Projects/Rawl
    python scripts/init-platform.py

Prerequisites:
    - Solana test validator running (localhost:8899)
    - Contract deployed (PROGRAM_ID set in .env)
    - Oracle keypair at ./oracle-keypair.json
    - Wallet at ~/.config/solana/id.json (authority + treasury for dev)
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, "packages/backend/src")


async def main():
    from rawl.config import settings
    from rawl.solana.client import solana_client
    from rawl.solana.instructions import build_initialize_ix
    from rawl.solana.pda import derive_platform_config_pda

    # Load oracle pubkey
    oracle_path = Path(settings.oracle_keypair_path)
    if not oracle_path.exists():
        print(f"ERROR: Oracle keypair not found at {oracle_path}")
        return

    with open(oracle_path) as f:
        oracle_bytes = bytes(json.load(f))

    from solders.keypair import Keypair
    from solders.pubkey import Pubkey

    oracle_kp = Keypair.from_bytes(oracle_bytes)
    oracle_pubkey = oracle_kp.pubkey()
    print(f"Oracle pubkey: {oracle_pubkey}")

    # Initialize Solana client (loads wallet keypair as authority)
    await solana_client.initialize()
    authority_pubkey = solana_client.oracle_keypair.pubkey()
    print(f"Authority pubkey (wallet): {authority_pubkey}")

    # For local dev, use the wallet as treasury too
    treasury_pubkey = authority_pubkey
    print(f"Treasury pubkey: {treasury_pubkey}")

    # Check if already initialized
    platform_config_pda, bump = derive_platform_config_pda()
    print(f"PlatformConfig PDA: {platform_config_pda} (bump: {bump})")

    existing = await solana_client.get_platform_config()
    if existing:
        print(f"PlatformConfig already initialized!")
        print(f"  authority: {existing.authority}")
        print(f"  oracle: {existing.oracle}")
        print(f"  fee_bps: {existing.fee_bps}")
        print(f"  treasury: {existing.treasury}")
        print(f"  paused: {existing.paused}")
        await solana_client.close()
        return

    # Build and send initialize instruction
    # For dev: authority = oracle keypair (same wallet)
    fee_bps = 300  # 3%
    match_timeout = 1800  # 30 minutes

    ix = build_initialize_ix(
        authority=authority_pubkey,
        oracle=oracle_pubkey,
        treasury=treasury_pubkey,
        fee_bps=fee_bps,
        match_timeout=match_timeout,
    )

    print(f"\nSending initialize transaction...")
    print(f"  fee_bps: {fee_bps} (3%)")
    print(f"  match_timeout: {match_timeout}s")

    try:
        sig = await solana_client._build_and_send(ix, "initialize")
        print(f"Transaction confirmed: {sig}")
    except Exception as e:
        print(f"ERROR: {e}")
        await solana_client.close()
        return

    # Verify
    config = await solana_client.get_platform_config()
    if config:
        print(f"\nPlatformConfig initialized successfully!")
        print(f"  authority: {config.authority}")
        print(f"  oracle: {config.oracle}")
        print(f"  fee_bps: {config.fee_bps}")
        print(f"  treasury: {config.treasury}")
    else:
        print("WARNING: Could not verify PlatformConfig")

    await solana_client.close()


if __name__ == "__main__":
    asyncio.run(main())
