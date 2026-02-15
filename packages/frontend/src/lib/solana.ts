/**
 * Solana transaction builders for betting.
 *
 * These construct and sign transactions via the wallet adapter.
 * The actual instruction layout matches the Anchor program in packages/contracts.
 */

import { BetSide } from "@rawl/shared";

const PROGRAM_ID = process.env.NEXT_PUBLIC_PROGRAM_ID ?? "";

export async function placeBetTransaction(
  matchId: string,
  side: BetSide,
  amountSol: number,
): Promise<string> {
  // Dynamic imports to avoid SSR issues with Solana libs
  const { PublicKey, SystemProgram, Transaction, LAMPORTS_PER_SOL } = await import(
    "@solana/web3.js"
  );
  const { useWallet, useConnection } = await import("@solana/wallet-adapter-react");

  // This function is called from component context where wallet/connection are available.
  // We throw here; the caller should handle via the adapter hooks directly.
  throw new Error(
    "placeBetTransaction must be called from a component with wallet context. " +
      "Use the usePlaceBet hook instead.",
  );
}

/**
 * Derive a PDA for the match pool.
 */
export async function deriveMatchPoolPda(matchId: string) {
  const { PublicKey } = await import("@solana/web3.js");
  const programId = new PublicKey(PROGRAM_ID);
  const encoder = new TextEncoder();
  const [pda] = PublicKey.findProgramAddressSync(
    [encoder.encode("match_pool"), encoder.encode(matchId.replace(/-/g, "").slice(0, 32))],
    programId,
  );
  return pda;
}

/**
 * Derive a PDA for a bet.
 */
export async function deriveBetPda(matchId: string, bettor: string) {
  const { PublicKey } = await import("@solana/web3.js");
  const programId = new PublicKey(PROGRAM_ID);
  const encoder = new TextEncoder();
  const bettorKey = new PublicKey(bettor);
  const [pda] = PublicKey.findProgramAddressSync(
    [
      encoder.encode("bet"),
      encoder.encode(matchId.replace(/-/g, "").slice(0, 32)),
      bettorKey.toBuffer(),
    ],
    programId,
  );
  return pda;
}
