export const CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_CONTRACT_ADDRESS as `0x${string}` | undefined

/**
 * Convert a UUID string to bytes32 hex for the contract.
 * Same logic as backend match_id_to_bytes(): UUID hex (16 bytes) + 16 zero bytes.
 */
export function matchIdToBytes32(matchId: string): `0x${string}` {
  const hex = matchId.replace(/-/g, '') // 32 hex chars = 16 bytes
  return `0x${hex.padEnd(64, '0')}` as `0x${string}` // pad to 64 hex chars = 32 bytes
}

export const BETTING_ABI = [
  // createMatch
  {
    type: 'function',
    name: 'createMatch',
    inputs: [
      { name: 'matchId', type: 'bytes32' },
      { name: 'fighterA', type: 'address' },
      { name: 'fighterB', type: 'address' },
      { name: 'minBet', type: 'uint128' },
      { name: 'bettingWindow', type: 'uint64' },
    ],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // placeBet
  {
    type: 'function',
    name: 'placeBet',
    inputs: [
      { name: 'matchId', type: 'bytes32' },
      { name: 'side', type: 'uint8' },
    ],
    outputs: [],
    stateMutability: 'payable',
  },
  // lockMatch
  {
    type: 'function',
    name: 'lockMatch',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // resolveMatch
  {
    type: 'function',
    name: 'resolveMatch',
    inputs: [
      { name: 'matchId', type: 'bytes32' },
      { name: 'winner', type: 'uint8' },
    ],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // claimPayout
  {
    type: 'function',
    name: 'claimPayout',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // refundNoWinners
  {
    type: 'function',
    name: 'refundNoWinners',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // cancelMatch
  {
    type: 'function',
    name: 'cancelMatch',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // timeoutMatch
  {
    type: 'function',
    name: 'timeoutMatch',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // refundBet
  {
    type: 'function',
    name: 'refundBet',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [],
    stateMutability: 'nonpayable',
  },
  // matches mapping reader
  {
    type: 'function',
    name: 'matches',
    inputs: [{ name: 'matchId', type: 'bytes32' }],
    outputs: [
      { name: 'fighterA', type: 'address' },
      { name: 'fighterB', type: 'address' },
      { name: 'status', type: 'uint8' },
      { name: 'winner', type: 'uint8' },
      { name: 'sideABetCount', type: 'uint32' },
      { name: 'sideBBetCount', type: 'uint32' },
      { name: 'winningBetCount', type: 'uint32' },
      { name: 'betCount', type: 'uint32' },
      { name: 'feeBps', type: 'uint16' },
      { name: 'sideATotal', type: 'uint128' },
      { name: 'sideBTotal', type: 'uint128' },
      { name: 'createdAt', type: 'uint64' },
      { name: 'lockTimestamp', type: 'uint64' },
      { name: 'resolveTimestamp', type: 'uint64' },
      { name: 'cancelTimestamp', type: 'uint64' },
      { name: 'minBet', type: 'uint128' },
      { name: 'bettingWindow', type: 'uint64' },
      { name: 'feesWithdrawn', type: 'bool' },
    ],
    stateMutability: 'view',
  },
  // bets mapping reader
  {
    type: 'function',
    name: 'bets',
    inputs: [
      { name: 'matchId', type: 'bytes32' },
      { name: 'bettor', type: 'address' },
    ],
    outputs: [
      { name: 'amount', type: 'uint128' },
      { name: 'side', type: 'uint8' },
      { name: 'claimed', type: 'bool' },
    ],
    stateMutability: 'view',
  },
  // Events
  {
    type: 'event',
    name: 'BetPlaced',
    inputs: [
      { name: 'matchId', type: 'bytes32', indexed: true },
      { name: 'bettor', type: 'address', indexed: true },
      { name: 'side', type: 'uint8', indexed: false },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
  {
    type: 'event',
    name: 'PayoutClaimed',
    inputs: [
      { name: 'matchId', type: 'bytes32', indexed: true },
      { name: 'bettor', type: 'address', indexed: true },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
  {
    type: 'event',
    name: 'BetRefunded',
    inputs: [
      { name: 'matchId', type: 'bytes32', indexed: true },
      { name: 'bettor', type: 'address', indexed: true },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
  {
    type: 'event',
    name: 'NoWinnersRefunded',
    inputs: [
      { name: 'matchId', type: 'bytes32', indexed: true },
      { name: 'bettor', type: 'address', indexed: true },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
] as const
