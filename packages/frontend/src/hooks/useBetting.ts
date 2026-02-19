"use client";

import { useState, useCallback } from "react";
import { useAccount, usePublicClient, useWriteContract } from "wagmi";
import { parseEther } from "viem";
import { BetSide } from "@/types";
import { CONTRACT_ADDRESS, BETTING_ABI, matchIdToBytes32 } from "@/lib/contracts";
import { syncBetStatus } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080/api";

/**
 * Hook for placing bets on Base and recording them in the backend.
 */
export function usePlaceBet() {
  const { address } = useAccount();
  const publicClient = usePublicClient();
  const { writeContractAsync } = useWriteContract();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const placeBet = useCallback(
    async (matchId: string, side: BetSide, amountEth: number): Promise<string | null> => {
      if (!address) {
        setError("Wallet not connected");
        return null;
      }
      if (!CONTRACT_ADDRESS) {
        setError("Contract address not configured");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const sideNum = side === "a" ? 0 : 1;
        const hash = await writeContractAsync({
          address: CONTRACT_ADDRESS,
          abi: BETTING_ABI,
          functionName: 'placeBet',
          args: [matchIdToBytes32(matchId), sideNum],
          value: parseEther(amountEth.toString()),
        });
        await publicClient!.waitForTransactionReceipt({ hash, confirmations: 1 });

        // Record the bet in the backend for tracking (non-critical)
        try {
          await fetch(`${API_URL}/matches/${matchId}/bets`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              wallet_address: address,
              side,
              amount_eth: amountEth,
              tx_hash: hash,
            }),
          });
        } catch {
          console.warn("Failed to record bet in backend");
        }

        return hash;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to place bet";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [address, publicClient, writeContractAsync],
  );

  return { placeBet, submitting, error };
}

/**
 * Hook for claiming payouts after a match resolves.
 */
export function useClaimPayout() {
  const { address } = useAccount();
  const publicClient = usePublicClient();
  const { writeContractAsync } = useWriteContract();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const claimPayout = useCallback(
    async (matchId: string, betId?: string): Promise<string | null> => {
      if (!address) {
        setError("Wallet not connected");
        return null;
      }
      if (!CONTRACT_ADDRESS) {
        setError("Contract address not configured");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const hash = await writeContractAsync({
          address: CONTRACT_ADDRESS,
          abi: BETTING_ABI,
          functionName: 'claimPayout',
          args: [matchIdToBytes32(matchId)],
        });
        await publicClient!.waitForTransactionReceipt({ hash, confirmations: 1 });

        // Sync bet status in backend (non-critical)
        if (betId) {
          try {
            await syncBetStatus(betId, address);
          } catch {
            console.warn("Failed to sync bet status after claim");
          }
        }

        return hash;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to claim payout";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [address, publicClient, writeContractAsync],
  );

  return { claimPayout, submitting, error };
}

/**
 * Hook for refunding bets on cancelled matches.
 */
export function useRefundBet() {
  const { address } = useAccount();
  const publicClient = usePublicClient();
  const { writeContractAsync } = useWriteContract();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refundBet = useCallback(
    async (matchId: string, betId?: string): Promise<string | null> => {
      if (!address) {
        setError("Wallet not connected");
        return null;
      }
      if (!CONTRACT_ADDRESS) {
        setError("Contract address not configured");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const hash = await writeContractAsync({
          address: CONTRACT_ADDRESS,
          abi: BETTING_ABI,
          functionName: 'refundBet',
          args: [matchIdToBytes32(matchId)],
        });
        await publicClient!.waitForTransactionReceipt({ hash, confirmations: 1 });

        // Sync bet status in backend (non-critical)
        if (betId) {
          try {
            await syncBetStatus(betId, address);
          } catch {
            console.warn("Failed to sync bet status after refund");
          }
        }

        return hash;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to refund bet";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [address, publicClient, writeContractAsync],
  );

  return { refundBet, submitting, error };
}

/**
 * Hook for refunding bets when a match resolves with no winners on the winning side.
 */
export function useRefundNoWinners() {
  const { address } = useAccount();
  const publicClient = usePublicClient();
  const { writeContractAsync } = useWriteContract();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refundNoWinners = useCallback(
    async (matchId: string, betId?: string): Promise<string | null> => {
      if (!address) {
        setError("Wallet not connected");
        return null;
      }
      if (!CONTRACT_ADDRESS) {
        setError("Contract address not configured");
        return null;
      }

      setSubmitting(true);
      setError(null);

      try {
        const hash = await writeContractAsync({
          address: CONTRACT_ADDRESS,
          abi: BETTING_ABI,
          functionName: 'refundNoWinners',
          args: [matchIdToBytes32(matchId)],
        });
        await publicClient!.waitForTransactionReceipt({ hash, confirmations: 1 });

        // Sync bet status in backend (non-critical)
        if (betId) {
          try {
            await syncBetStatus(betId, address);
          } catch {
            console.warn("Failed to sync bet status after no-winners refund");
          }
        }

        return hash;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to refund bet";
        setError(msg);
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [address, publicClient, writeContractAsync],
  );

  return { refundNoWinners, submitting, error };
}
