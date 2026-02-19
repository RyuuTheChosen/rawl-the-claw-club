// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/RawlBetting.sol";

/// @notice Handler for invariant testing — simulates random user actions
contract Handler is Test {
    RawlBetting public betting;
    address public admin;
    address public oracle;

    uint256 public ghost_totalDeposited;
    uint256 public ghost_totalWithdrawn;

    uint256 private matchCount;
    bytes32[] private activeMatches;
    address[] private bettors;

    constructor(RawlBetting _betting, address _admin, address _oracle) {
        betting = _betting;
        admin = _admin;
        oracle = _oracle;

        // Pre-create bettors with funds
        for (uint256 i = 0; i < 10; i++) {
            address bettor = makeAddr(string(abi.encodePacked("bettor", i)));
            vm.deal(bettor, 1000 ether);
            bettors.push(bettor);
        }
    }

    function createMatch(uint256 seed) external {
        matchCount++;
        bytes32 mId = keccak256(abi.encodePacked("invariant-match", matchCount));
        activeMatches.push(mId);

        vm.prank(oracle);
        betting.createMatch(mId, makeAddr("fA"), makeAddr("fB"), 0.001 ether, 0);
    }

    function placeBet(uint256 matchSeed, uint256 bettorSeed, uint128 amount) external {
        if (activeMatches.length == 0) return;

        bytes32 mId = activeMatches[matchSeed % activeMatches.length];
        address bettor = bettors[bettorSeed % bettors.length];
        amount = uint128(bound(amount, 0.001 ether, 10 ether));
        uint8 side = uint8(bettorSeed % 2);

        // Check match is open and bettor hasn't bet yet
        (,,RawlBetting.MatchStatus status,,,,,,,,,,,,,,,) = betting.matches(mId);
        if (status != RawlBetting.MatchStatus.Open) return;

        (uint128 existingAmount,,) = betting.bets(mId, bettor);
        if (existingAmount > 0) return;

        vm.prank(bettor);
        try betting.placeBet{value: amount}(mId, side) {
            ghost_totalDeposited += amount;
        } catch {}
    }

    function lockAndResolve(uint256 matchSeed, uint8 winner) external {
        if (activeMatches.length == 0) return;

        bytes32 mId = activeMatches[matchSeed % activeMatches.length];
        winner = winner % 2;

        (,,RawlBetting.MatchStatus status,,,,,,,,,,,,,,,) = betting.matches(mId);
        if (status != RawlBetting.MatchStatus.Open) return;

        vm.prank(oracle);
        try betting.lockMatch(mId) {} catch { return; }

        vm.prank(oracle);
        try betting.resolveMatch(mId, winner) {} catch {}
    }

    function claimPayout(uint256 matchSeed, uint256 bettorSeed) external {
        if (activeMatches.length == 0) return;

        bytes32 mId = activeMatches[matchSeed % activeMatches.length];
        address bettor = bettors[bettorSeed % bettors.length];

        uint256 balBefore = bettor.balance;
        vm.prank(bettor);
        try betting.claimPayout(mId) {
            ghost_totalWithdrawn += bettor.balance - balBefore;
        } catch {}
    }

    function cancelAndRefund(uint256 matchSeed, uint256 bettorSeed) external {
        if (activeMatches.length == 0) return;

        bytes32 mId = activeMatches[matchSeed % activeMatches.length];
        address bettor = bettors[bettorSeed % bettors.length];

        (,,RawlBetting.MatchStatus status,,,,,,,,,,,,,,,) = betting.matches(mId);
        if (status != RawlBetting.MatchStatus.Open && status != RawlBetting.MatchStatus.Locked) return;

        vm.prank(admin);
        try betting.cancelMatch(mId) {} catch { return; }

        uint256 balBefore = bettor.balance;
        vm.prank(bettor);
        try betting.refundBet(mId) {
            ghost_totalWithdrawn += bettor.balance - balBefore;
        } catch {}
    }
}
