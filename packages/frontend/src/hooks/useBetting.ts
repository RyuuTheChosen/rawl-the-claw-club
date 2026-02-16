"use client";

import { useState, useCallback } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { BetSide } from "@rawl/shared";
import {
  PROGRAM_ID,
  deriveMatchPoolPda,
  deriveBetPda,
  deriveVaultPda,
  derivePlatformConfigPda,
  buildPlaceBetData,
  buildClaimPayoutData,
  buildRefundBetData,
} from "@/lib/solana";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080/api";

/**
 * Hook for placing bets on Solana and recording them in the backend.
 */
export function usePlaceBet() {
  const { publicKey, sendTransaction } = useWallet();
  const { connection } = useConnection();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const placeBet = useCallback(
    async (matchId: string, side: BetSide, amountSol: number): Promise<string | null> => {
      if (!publicKey) {
        setError("Wallet not connected");
        return null;
      }
      if (!PROGRAM_ID) {
        setError("Program ID not configured");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const { PublicKey, TransactionInstruction, Transaction, SystemProgram, LAMPORTS_PER_SOL } =
          await import("@solana/web3.js");

        const programId = new PublicKey(PROGRAM_ID);
        const amountLamports = BigInt(Math.round(amountSol * LAMPORTS_PER_SOL));

        // Derive all PDAs
        const matchPoolPda = await deriveMatchPoolPda(matchId);
        const betPda = await deriveBetPda(matchId, publicKey.toBase58());
        const vaultPda = await deriveVaultPda(matchId);

        // Build instruction data
        const data = await buildPlaceBetData(matchId, side, amountLamports);

        // Build instruction with accounts matching place_bet.rs
        const instruction = new TransactionInstruction({
          programId,
          keys: [
            { pubkey: matchPoolPda, isSigner: false, isWritable: true },
            { pubkey: betPda, isSigner: false, isWritable: true },
            { pubkey: vaultPda, isSigner: false, isWritable: true },
            { pubkey: publicKey, isSigner: true, isWritable: true },
            { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
          ],
          data,
        });

        const tx = new Transaction().add(instruction);
        const signature = await sendTransaction(tx, connection);
        await connection.confirmTransaction(signature, "confirmed");

        // Record the bet in the backend for tracking
        try {
          await fetch(`${API_URL}/matches/${matchId}/bets`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              wallet_address: publicKey.toBase58(),
              side,
              amount_sol: amountSol,
              tx_signature: signature,
            }),
          });
        } catch {
          // Non-critical: bet is on-chain even if backend record fails
          console.warn("Failed to record bet in backend");
        }

        return signature;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to place bet";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [publicKey, sendTransaction, connection],
  );

  return { placeBet, submitting, error };
}

/**
 * Hook for claiming payouts after a match resolves.
 */
export function useClaimPayout() {
  const { publicKey, sendTransaction } = useWallet();
  const { connection } = useConnection();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const claimPayout = useCallback(
    async (matchId: string): Promise<string | null> => {
      if (!publicKey) {
        setError("Wallet not connected");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const { PublicKey, TransactionInstruction, Transaction, SystemProgram } = await import(
          "@solana/web3.js"
        );

        const programId = new PublicKey(PROGRAM_ID);

        const matchPoolPda = await deriveMatchPoolPda(matchId);
        const betPda = await deriveBetPda(matchId, publicKey.toBase58());
        const vaultPda = await deriveVaultPda(matchId);
        const platformConfigPda = await derivePlatformConfigPda();

        const data = await buildClaimPayoutData(matchId);

        // Accounts match claim_payout.rs
        const instruction = new TransactionInstruction({
          programId,
          keys: [
            { pubkey: matchPoolPda, isSigner: false, isWritable: true },
            { pubkey: betPda, isSigner: false, isWritable: true },
            { pubkey: vaultPda, isSigner: false, isWritable: true },
            { pubkey: platformConfigPda, isSigner: false, isWritable: false },
            { pubkey: publicKey, isSigner: true, isWritable: true },
            { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
          ],
          data,
        });

        const tx = new Transaction().add(instruction);
        const signature = await sendTransaction(tx, connection);
        await connection.confirmTransaction(signature, "confirmed");

        return signature;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to claim payout";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [publicKey, sendTransaction, connection],
  );

  return { claimPayout, submitting, error };
}

/**
 * Hook for refunding bets on cancelled matches.
 */
export function useRefundBet() {
  const { publicKey, sendTransaction } = useWallet();
  const { connection } = useConnection();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refundBet = useCallback(
    async (matchId: string): Promise<string | null> => {
      if (!publicKey) {
        setError("Wallet not connected");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const { PublicKey, TransactionInstruction, Transaction, SystemProgram } = await import(
          "@solana/web3.js"
        );

        const programId = new PublicKey(PROGRAM_ID);

        const matchPoolPda = await deriveMatchPoolPda(matchId);
        const betPda = await deriveBetPda(matchId, publicKey.toBase58());
        const vaultPda = await deriveVaultPda(matchId);

        const data = await buildRefundBetData(matchId);

        // Accounts match refund_bet.rs
        const instruction = new TransactionInstruction({
          programId,
          keys: [
            { pubkey: matchPoolPda, isSigner: false, isWritable: true },
            { pubkey: betPda, isSigner: false, isWritable: true },
            { pubkey: vaultPda, isSigner: false, isWritable: true },
            { pubkey: publicKey, isSigner: true, isWritable: true },
            { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
          ],
          data,
        });

        const tx = new Transaction().add(instruction);
        const signature = await sendTransaction(tx, connection);
        await connection.confirmTransaction(signature, "confirmed");

        return signature;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to refund bet";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [publicKey, sendTransaction, connection],
  );

  return { refundBet, submitting, error };
}
