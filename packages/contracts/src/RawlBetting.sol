// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/// @title RawlBetting — On-chain betting for AI fighting game matches
/// @notice Single contract managing all matches via mappings (replaces Solana Anchor program)
contract RawlBetting is AccessControl, ReentrancyGuard, Pausable {
    // ──────────────────────────────────────────────
    // Roles
    // ──────────────────────────────────────────────
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    // ──────────────────────────────────────────────
    // Constants
    // ──────────────────────────────────────────────
    uint16 public constant MAX_FEE_BPS = 1000; // 10% hard ceiling
    uint64 public constant DEFAULT_TIMEOUT = 1800; // 30 min
    uint64 public constant CLAIM_WINDOW = 30 days; // 2,592,000 seconds
    uint128 public constant DEFAULT_MIN_BET = 0.001 ether; // 1e15 wei

    // ──────────────────────────────────────────────
    // Enums
    // ──────────────────────────────────────────────
    enum MatchStatus { None, Open, Locked, Resolved, Cancelled }
    enum MatchWinner { None, SideA, SideB }

    // ──────────────────────────────────────────────
    // Structs (gas-optimized packed storage)
    // ──────────────────────────────────────────────
    struct MatchPool {
        // Slot 1
        address fighterA;
        // Slot 2
        address fighterB;
        // Slot 3 (packed: 1+1+4+4+4+4+2 = 20 bytes)
        MatchStatus status;
        MatchWinner winner;
        uint32 sideABetCount;
        uint32 sideBBetCount;
        uint32 winningBetCount;
        uint32 betCount;
        uint16 feeBps;
        // Slot 4 (packed: 16+16 = 32 bytes)
        uint128 sideATotal;
        uint128 sideBTotal;
        // Slot 5 (packed: 8+8+8+8 = 32 bytes)
        uint64 createdAt;
        uint64 lockTimestamp;
        uint64 resolveTimestamp;
        uint64 cancelTimestamp;
        // Slot 6 (packed: 16+8+1 = 25 bytes)
        uint128 minBet;
        uint64 bettingWindow;
        bool feesWithdrawn;
    }

    struct BetInfo {
        // Single slot (16+1+1 = 18 bytes)
        uint128 amount;
        uint8 side; // 0=SideA, 1=SideB
        bool claimed;
    }

    // ──────────────────────────────────────────────
    // State
    // ──────────────────────────────────────────────
    address public treasury;
    uint16 public feeBps;
    uint64 public matchTimeout;
    uint64 public claimWindow;

    mapping(bytes32 => MatchPool) public matches;
    mapping(bytes32 => mapping(address => BetInfo)) public bets;

    // ──────────────────────────────────────────────
    // Custom Errors
    // ──────────────────────────────────────────────
    error MatchAlreadyExists();
    error MatchNotOpen();
    error MatchNotLocked();
    error MatchNotResolved();
    error MatchNotCancelled();
    error InvalidSide();
    error ZeroBetAmount();
    error BetBelowMinimum(uint128 min);
    error BettingWindowClosed();
    error AlreadyBet();
    error NoBetFound();
    error AlreadyClaimed();
    error BetOnLosingSide();
    error WinnersExist();
    error TimeoutNotElapsed();
    error ClaimWindowNotElapsed();
    error FeesAlreadyWithdrawn();
    error WinningBetsRemaining();
    error TransferFailed();
    error InvalidFeeBps();
    error InvalidTimeout();
    error InvalidMatchStatus();

    // ──────────────────────────────────────────────
    // Events
    // ──────────────────────────────────────────────
    event MatchCreated(
        bytes32 indexed matchId,
        address fighterA,
        address fighterB,
        uint128 minBet,
        uint64 bettingWindow,
        uint16 feeBps
    );
    event MatchLocked(bytes32 indexed matchId, uint64 timestamp);
    event MatchResolved(
        bytes32 indexed matchId,
        uint8 winner,
        uint128 sideATotal,
        uint128 sideBTotal,
        uint64 timestamp
    );
    event MatchCancelled(bytes32 indexed matchId, uint64 timestamp);
    event BetPlaced(bytes32 indexed matchId, address indexed bettor, uint8 side, uint256 amount);
    event PayoutClaimed(bytes32 indexed matchId, address indexed bettor, uint256 amount);
    event BetRefunded(bytes32 indexed matchId, address indexed bettor, uint256 amount);
    event NoWinnersRefunded(bytes32 indexed matchId, address indexed bettor, uint256 amount);
    event FeesWithdrawn(bytes32 indexed matchId, uint256 amount, address treasury);
    event UnclaimedSwept(bytes32 indexed matchId, address indexed bettor, uint256 amount);
    event CancelledSwept(bytes32 indexed matchId, address indexed bettor, uint256 amount);
    event ConfigUpdated(string field, uint256 value);

    // ──────────────────────────────────────────────
    // Constructor
    // ──────────────────────────────────────────────
    constructor(address admin, address oracle, address _treasury) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(ORACLE_ROLE, oracle);
        treasury = _treasury;
        feeBps = 300; // 3%
        matchTimeout = DEFAULT_TIMEOUT;
        claimWindow = CLAIM_WINDOW;
    }

    // ──────────────────────────────────────────────
    // 1. createMatch
    // ──────────────────────────────────────────────
    function createMatch(
        bytes32 matchId,
        address fighterA,
        address fighterB,
        uint128 minBet,
        uint64 bettingWindow
    ) external whenNotPaused onlyRole(ORACLE_ROLE) {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.None) revert MatchAlreadyExists();

        pool.fighterA = fighterA;
        pool.fighterB = fighterB;
        pool.status = MatchStatus.Open;
        pool.feeBps = feeBps; // snapshot from global config
        pool.createdAt = uint64(block.timestamp);
        pool.minBet = minBet;
        pool.bettingWindow = bettingWindow;

        emit MatchCreated(matchId, fighterA, fighterB, minBet, bettingWindow, feeBps);
    }

    // ──────────────────────────────────────────────
    // 2. placeBet
    // ──────────────────────────────────────────────
    function placeBet(bytes32 matchId, uint8 side) external payable whenNotPaused nonReentrant {
        if (side > 1) revert InvalidSide();
        if (msg.value == 0) revert ZeroBetAmount();

        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Open) revert MatchNotOpen();

        if (pool.minBet > 0 && msg.value < pool.minBet) {
            revert BetBelowMinimum(pool.minBet);
        }
        if (pool.bettingWindow > 0 && block.timestamp > pool.createdAt + pool.bettingWindow) {
            revert BettingWindowClosed();
        }

        BetInfo storage bet = bets[matchId][msg.sender];
        if (bet.amount > 0) revert AlreadyBet();

        bet.amount = uint128(msg.value);
        bet.side = side;

        if (side == 0) {
            pool.sideATotal += uint128(msg.value);
            unchecked { pool.sideABetCount++; }
        } else {
            pool.sideBTotal += uint128(msg.value);
            unchecked { pool.sideBBetCount++; }
        }
        unchecked { pool.betCount++; }

        emit BetPlaced(matchId, msg.sender, side, msg.value);
    }

    // ──────────────────────────────────────────────
    // 3. lockMatch
    // ──────────────────────────────────────────────
    function lockMatch(bytes32 matchId) external onlyRole(ORACLE_ROLE) {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Open) revert MatchNotOpen();

        pool.status = MatchStatus.Locked;
        pool.lockTimestamp = uint64(block.timestamp);

        emit MatchLocked(matchId, uint64(block.timestamp));
    }

    // ──────────────────────────────────────────────
    // 4. resolveMatch
    // ──────────────────────────────────────────────
    function resolveMatch(bytes32 matchId, uint8 winner) external onlyRole(ORACLE_ROLE) {
        if (winner > 1) revert InvalidSide();

        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Locked) revert MatchNotLocked();

        pool.status = MatchStatus.Resolved;
        pool.winner = winner == 0 ? MatchWinner.SideA : MatchWinner.SideB;
        pool.resolveTimestamp = uint64(block.timestamp);
        pool.winningBetCount = winner == 0 ? pool.sideABetCount : pool.sideBBetCount;

        emit MatchResolved(
            matchId,
            winner,
            pool.sideATotal,
            pool.sideBTotal,
            uint64(block.timestamp)
        );
    }

    // ──────────────────────────────────────────────
    // 5. claimPayout
    // ──────────────────────────────────────────────
    function claimPayout(bytes32 matchId) external nonReentrant {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Resolved) revert MatchNotResolved();

        BetInfo storage bet = bets[matchId][msg.sender];
        if (bet.amount == 0) revert NoBetFound();
        if (bet.claimed) revert AlreadyClaimed();

        uint8 winningSide = pool.winner == MatchWinner.SideA ? 0 : 1;
        if (bet.side != winningSide) revert BetOnLosingSide();

        uint256 payout = _calculatePayout(pool, bet.amount);

        // CEI: effects before interaction
        bet.claimed = true;
        unchecked { pool.winningBetCount--; }
        unchecked { pool.betCount--; }

        (bool success,) = payable(msg.sender).call{value: payout}("");
        if (!success) revert TransferFailed();

        emit PayoutClaimed(matchId, msg.sender, payout);
    }

    // ──────────────────────────────────────────────
    // 6. refundNoWinners
    // ──────────────────────────────────────────────
    function refundNoWinners(bytes32 matchId) external nonReentrant {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Resolved) revert MatchNotResolved();
        if (pool.winningBetCount > 0) revert WinnersExist();

        BetInfo storage bet = bets[matchId][msg.sender];
        if (bet.amount == 0) revert NoBetFound();
        if (bet.claimed) revert AlreadyClaimed();

        // Fee IS deducted even on no-winner refunds
        uint256 refundAmount = (uint256(bet.amount) * (10_000 - pool.feeBps)) / 10_000;

        bet.claimed = true;
        unchecked { pool.betCount--; }

        (bool success,) = payable(msg.sender).call{value: refundAmount}("");
        if (!success) revert TransferFailed();

        emit NoWinnersRefunded(matchId, msg.sender, refundAmount);
    }

    // ──────────────────────────────────────────────
    // 7. cancelMatch
    // ──────────────────────────────────────────────
    function cancelMatch(bytes32 matchId) external onlyRole(ADMIN_ROLE) {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Open && pool.status != MatchStatus.Locked) {
            revert InvalidMatchStatus();
        }

        pool.status = MatchStatus.Cancelled;
        pool.cancelTimestamp = uint64(block.timestamp);

        emit MatchCancelled(matchId, uint64(block.timestamp));
    }

    // ──────────────────────────────────────────────
    // 8. timeoutMatch (permissionless)
    // ──────────────────────────────────────────────
    function timeoutMatch(bytes32 matchId) external {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Locked) revert MatchNotLocked();
        if (block.timestamp < pool.lockTimestamp + matchTimeout) revert TimeoutNotElapsed();

        pool.status = MatchStatus.Cancelled;
        pool.cancelTimestamp = uint64(block.timestamp);

        emit MatchCancelled(matchId, uint64(block.timestamp));
    }

    // ──────────────────────────────────────────────
    // 9. refundBet (cancelled matches — FULL refund, NO fee)
    // ──────────────────────────────────────────────
    function refundBet(bytes32 matchId) external nonReentrant {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Cancelled) revert MatchNotCancelled();

        BetInfo storage bet = bets[matchId][msg.sender];
        if (bet.amount == 0) revert NoBetFound();
        if (bet.claimed) revert AlreadyClaimed();

        uint256 refundAmount = uint256(bet.amount);

        bet.claimed = true;
        unchecked { pool.betCount--; }

        (bool success,) = payable(msg.sender).call{value: refundAmount}("");
        if (!success) revert TransferFailed();

        emit BetRefunded(matchId, msg.sender, refundAmount);
    }

    // ──────────────────────────────────────────────
    // 10. withdrawFees
    // ──────────────────────────────────────────────
    function withdrawFees(bytes32 matchId) external onlyRole(ADMIN_ROLE) nonReentrant {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Resolved) revert MatchNotResolved();
        if (pool.feesWithdrawn) revert FeesAlreadyWithdrawn();
        if (pool.winningBetCount > 0) revert WinningBetsRemaining();
        if (block.timestamp < pool.resolveTimestamp + claimWindow) revert ClaimWindowNotElapsed();

        uint256 totalPool = uint256(pool.sideATotal) + uint256(pool.sideBTotal);
        uint256 fee = (totalPool * pool.feeBps) / 10_000;
        // Use min(fee, balance) to handle rounding dust
        uint256 amount = fee < address(this).balance ? fee : address(this).balance;

        pool.feesWithdrawn = true;

        (bool success,) = payable(treasury).call{value: amount}("");
        if (!success) revert TransferFailed();

        emit FeesWithdrawn(matchId, amount, treasury);
    }

    // ──────────────────────────────────────────────
    // 11. sweepUnclaimed (unclaimed winning bets → treasury)
    // ──────────────────────────────────────────────
    function sweepUnclaimed(bytes32 matchId, address bettor)
        external
        onlyRole(ADMIN_ROLE)
        nonReentrant
    {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Resolved) revert MatchNotResolved();
        if (block.timestamp < pool.resolveTimestamp + claimWindow) revert ClaimWindowNotElapsed();

        BetInfo storage bet = bets[matchId][bettor];
        if (bet.amount == 0) revert NoBetFound();
        if (bet.claimed) revert AlreadyClaimed();

        uint8 winningSide = pool.winner == MatchWinner.SideA ? 0 : 1;
        if (bet.side != winningSide) revert BetOnLosingSide();

        uint256 payout = _calculatePayout(pool, bet.amount);

        bet.claimed = true;
        unchecked { pool.winningBetCount--; }
        unchecked { pool.betCount--; }

        (bool success,) = payable(treasury).call{value: payout}("");
        if (!success) revert TransferFailed();

        emit UnclaimedSwept(matchId, bettor, payout);
    }

    // ──────────────────────────────────────────────
    // 12. sweepCancelled (uncollected refunds → original bettor)
    // ──────────────────────────────────────────────
    function sweepCancelled(bytes32 matchId, address bettor) external nonReentrant {
        MatchPool storage pool = matches[matchId];
        if (pool.status != MatchStatus.Cancelled) revert MatchNotCancelled();
        if (block.timestamp < pool.cancelTimestamp + claimWindow) revert ClaimWindowNotElapsed();

        BetInfo storage bet = bets[matchId][bettor];
        if (bet.amount == 0) revert NoBetFound();
        if (bet.claimed) revert AlreadyClaimed();

        uint256 refundAmount = uint256(bet.amount);

        bet.claimed = true;
        unchecked { pool.betCount--; }

        // Returns to original bettor (NOT treasury) — matches Solana behavior
        (bool success,) = payable(bettor).call{value: refundAmount}("");
        if (!success) revert TransferFailed();

        emit CancelledSwept(matchId, bettor, refundAmount);
    }

    // ──────────────────────────────────────────────
    // 13. updateConfig
    // ──────────────────────────────────────────────
    function updateConfig(uint16 newFeeBps, uint64 newTimeout, address newTreasury)
        external
        onlyRole(ADMIN_ROLE)
    {
        if (newFeeBps > 0) {
            if (newFeeBps > MAX_FEE_BPS) revert InvalidFeeBps();
            feeBps = newFeeBps;
            emit ConfigUpdated("feeBps", uint256(newFeeBps));
        }
        if (newTimeout > 0) {
            matchTimeout = newTimeout;
            emit ConfigUpdated("matchTimeout", uint256(newTimeout));
        }
        if (newTreasury != address(0)) {
            treasury = newTreasury;
            emit ConfigUpdated("treasury", uint256(uint160(newTreasury)));
        }
    }

    // ──────────────────────────────────────────────
    // 14. pause / unpause
    // ──────────────────────────────────────────────
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }

    // ──────────────────────────────────────────────
    // Internal: Payout math
    // ──────────────────────────────────────────────
    function _calculatePayout(MatchPool storage pool, uint128 betAmount)
        internal
        view
        returns (uint256)
    {
        uint256 totalPool = uint256(pool.sideATotal) + uint256(pool.sideBTotal);
        uint256 fee = (totalPool * pool.feeBps) / 10_000;
        uint256 netPool = totalPool - fee;
        uint256 winningSideTotal = pool.winner == MatchWinner.SideA
            ? uint256(pool.sideATotal)
            : uint256(pool.sideBTotal);
        return (netPool * uint256(betAmount)) / winningSideTotal;
    }

    // No receive() or fallback() — ETH only enters via placeBet
}
