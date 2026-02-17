/**
 * Solana PDA derivation and instruction data builders for the Rawl program.
 *
 * PDA seeds must match the Anchor contract in packages/contracts:
 *   match_pool: ["match_pool", match_id_bytes(32)]
 *   bet:        ["bet", match_id_bytes(32), bettor_pubkey(32)]
 *   vault:      ["vault", match_id_bytes(32)]
 *   platform_config: ["platform_config"]
 */

import { BetSide } from "@/types";

export const PROGRAM_ID = process.env.NEXT_PUBLIC_PROGRAM_ID ?? "";

/**
 * Convert a UUID string to 32 zero-padded bytes matching backend's match_id_to_bytes().
 * UUID is 16 bytes, padded with 16 zero bytes to fill 32.
 */
export function matchIdToBytes(matchId: string): Uint8Array {
  const hex = matchId.replace(/-/g, "");
  const bytes = new Uint8Array(32); // 32 bytes, zero-filled
  for (let i = 0; i < 16; i++) {
    bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

/**
 * Compute Anchor instruction discriminator: SHA256("global:<name>")[:8]
 */
async function anchorDiscriminator(name: string): Promise<Uint8Array> {
  const data = new TextEncoder().encode(`global:${name}`);
  const hash = await crypto.subtle.digest("SHA-256", new Uint8Array(data));
  return new Uint8Array(hash).slice(0, 8);
}

/**
 * Derive the MatchPool PDA.
 */
export async function deriveMatchPoolPda(matchId: string) {
  const { PublicKey } = await import("@solana/web3.js");
  const programId = new PublicKey(PROGRAM_ID);
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("match_pool"), matchIdToBytes(matchId)],
    programId,
  );
  return pda;
}

/**
 * Derive the Bet PDA for a bettor on a match.
 */
export async function deriveBetPda(matchId: string, bettor: string) {
  const { PublicKey } = await import("@solana/web3.js");
  const programId = new PublicKey(PROGRAM_ID);
  const bettorKey = new PublicKey(bettor);
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("bet"), matchIdToBytes(matchId), bettorKey.toBuffer()],
    programId,
  );
  return pda;
}

/**
 * Derive the Vault PDA for a match.
 */
export async function deriveVaultPda(matchId: string) {
  const { PublicKey } = await import("@solana/web3.js");
  const programId = new PublicKey(PROGRAM_ID);
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("vault"), matchIdToBytes(matchId)],
    programId,
  );
  return pda;
}

/**
 * Derive the PlatformConfig PDA.
 */
export async function derivePlatformConfigPda() {
  const { PublicKey } = await import("@solana/web3.js");
  const programId = new PublicKey(PROGRAM_ID);
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("platform_config")],
    programId,
  );
  return pda;
}

/**
 * Build the instruction data for place_bet.
 * Layout: discriminator(8) + match_id(32) + side(1) + amount(8)
 */
export async function buildPlaceBetData(
  matchId: string,
  side: BetSide,
  amountLamports: bigint,
): Promise<Buffer> {
  const disc = await anchorDiscriminator("place_bet");
  const midBytes = matchIdToBytes(matchId);
  const sideU8 = side === "a" ? 0 : 1;

  const buf = Buffer.alloc(8 + 32 + 1 + 8);
  buf.set(disc, 0);
  buf.set(midBytes, 8);
  buf.writeUInt8(sideU8, 40);
  buf.writeBigUInt64LE(amountLamports, 41);
  return buf;
}

/**
 * Build the instruction data for claim_payout.
 * Layout: discriminator(8) + match_id(32)
 */
export async function buildClaimPayoutData(matchId: string): Promise<Buffer> {
  const disc = await anchorDiscriminator("claim_payout");
  const midBytes = matchIdToBytes(matchId);

  const buf = Buffer.alloc(8 + 32);
  buf.set(disc, 0);
  buf.set(midBytes, 8);
  return buf;
}

/**
 * Build the instruction data for refund_bet.
 * Layout: discriminator(8) + match_id(32)
 */
export async function buildRefundBetData(matchId: string): Promise<Buffer> {
  const disc = await anchorDiscriminator("refund_bet");
  const midBytes = matchIdToBytes(matchId);

  const buf = Buffer.alloc(8 + 32);
  buf.set(disc, 0);
  buf.set(midBytes, 8);
  return buf;
}
