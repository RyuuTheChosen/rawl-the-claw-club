// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/RawlBetting.sol";

contract RawlBettingTest is Test {
    RawlBetting public betting;

    address admin = makeAddr("admin");
    address oracle = makeAddr("oracle");
    address treasury = makeAddr("treasury");
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");
    address charlie = makeAddr("charlie");

    bytes32 matchId = keccak256("match-1");

    function setUp() public {
        betting = new RawlBetting(admin, oracle, treasury);
        vm.deal(alice, 100 ether);
        vm.deal(bob, 100 ether);
        vm.deal(charlie, 100 ether);
    }

    // ─── Helpers ───

    function _createMatch() internal {
        vm.prank(oracle);
        betting.createMatch(matchId, makeAddr("fighterA"), makeAddr("fighterB"), 0.001 ether, 0);
    }

    function _createAndBetBothSides() internal {
        _createMatch();
        vm.prank(alice);
        betting.placeBet{value: 1 ether}(matchId, 0); // Side A
        vm.prank(bob);
        betting.placeBet{value: 1 ether}(matchId, 1); // Side B
    }

    // ─── Full Lifecycle ───

    function test_FullLifecycle() public {
        // Create
        _createMatch();
        (,,RawlBetting.MatchStatus status,,,,,,,,,,,,,,,) = betting.matches(matchId);
        assertEq(uint8(status), uint8(RawlBetting.MatchStatus.Open));

        // Bet
        vm.prank(alice);
        betting.placeBet{value: 1 ether}(matchId, 0);
        vm.prank(bob);
        betting.placeBet{value: 2 ether}(matchId, 1);

        // Lock
        vm.prank(oracle);
        betting.lockMatch(matchId);

        // Resolve (Side A wins)
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);

        // Claim (Alice wins)
        uint256 aliceBefore = alice.balance;
        vm.prank(alice);
        betting.claimPayout(matchId);
        uint256 aliceAfter = alice.balance;

        // Payout: totalPool=3 ETH, fee=3*300/10000=0.09 ETH, netPool=2.91 ETH
        // Alice bet 1 ETH on winning side (1 ETH total), so payout = 2.91 ETH
        assertEq(aliceAfter - aliceBefore, 2.91 ether);

        // Withdraw fees after claim window
        vm.warp(block.timestamp + 30 days + 1);
        vm.prank(admin);
        betting.withdrawFees(matchId);
        assertGt(treasury.balance, 0);
    }

    // ─── Cancel Flow ───

    function test_CancelFlow() public {
        _createAndBetBothSides();

        vm.prank(admin);
        betting.cancelMatch(matchId);

        // Full refund (no fee)
        uint256 aliceBefore = alice.balance;
        vm.prank(alice);
        betting.refundBet(matchId);
        assertEq(alice.balance - aliceBefore, 1 ether);

        uint256 bobBefore = bob.balance;
        vm.prank(bob);
        betting.refundBet(matchId);
        assertEq(bob.balance - bobBefore, 1 ether);
    }

    // ─── Timeout Flow ───

    function test_TimeoutFlow() public {
        _createAndBetBothSides();

        vm.prank(oracle);
        betting.lockMatch(matchId);

        // Can't timeout yet
        vm.expectRevert(RawlBetting.TimeoutNotElapsed.selector);
        betting.timeoutMatch(matchId);

        // Warp past timeout
        vm.warp(block.timestamp + 1801);
        betting.timeoutMatch(matchId);

        // Now refund works
        vm.prank(alice);
        betting.refundBet(matchId);
    }

    // ─── No Winners Flow ───

    function test_NoWinnersFlow() public {
        _createMatch();

        // Only Alice bets on Side A
        vm.prank(alice);
        betting.placeBet{value: 1 ether}(matchId, 0);

        vm.prank(oracle);
        betting.lockMatch(matchId);

        // Resolve Side B wins (no bets on B)
        vm.prank(oracle);
        betting.resolveMatch(matchId, 1);

        // Alice gets refund minus fee
        uint256 aliceBefore = alice.balance;
        vm.prank(alice);
        betting.refundNoWinners(matchId);
        uint256 refund = alice.balance - aliceBefore;

        // 1 ETH * (10000 - 300) / 10000 = 0.97 ETH
        assertEq(refund, 0.97 ether);
    }

    // ─── Sweep Unclaimed ───

    function test_SweepUnclaimed() public {
        _createAndBetBothSides();

        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0); // Side A wins

        // Warp past claim window
        vm.warp(block.timestamp + 30 days + 1);

        // Sweep Alice's unclaimed payout to treasury
        uint256 treasuryBefore = treasury.balance;
        vm.prank(admin);
        betting.sweepUnclaimed(matchId, alice);
        assertGt(treasury.balance, treasuryBefore);
    }

    // ─── Sweep Cancelled ───

    function test_SweepCancelled() public {
        _createAndBetBothSides();

        vm.prank(admin);
        betting.cancelMatch(matchId);

        // Warp past claim window
        vm.warp(block.timestamp + 30 days + 1);

        // Anyone can sweep — goes to original bettor (not treasury)
        uint256 aliceBefore = alice.balance;
        betting.sweepCancelled(matchId, alice);
        assertEq(alice.balance - aliceBefore, 1 ether);
    }

    // ─── Access Control ───

    function test_NonOracleCantCreate() public {
        vm.prank(alice);
        vm.expectRevert();
        betting.createMatch(matchId, makeAddr("a"), makeAddr("b"), 0, 0);
    }

    function test_NonOracleCantLock() public {
        _createMatch();
        vm.prank(alice);
        vm.expectRevert();
        betting.lockMatch(matchId);
    }

    function test_NonOracleCantResolve() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);

        vm.prank(alice);
        vm.expectRevert();
        betting.resolveMatch(matchId, 0);
    }

    function test_NonAdminCantCancel() public {
        _createMatch();
        vm.prank(alice);
        vm.expectRevert();
        betting.cancelMatch(matchId);
    }

    function test_NonAdminCantWithdrawFees() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);
        vm.prank(alice);
        betting.claimPayout(matchId);
        vm.warp(block.timestamp + 30 days + 1);

        vm.prank(alice);
        vm.expectRevert();
        betting.withdrawFees(matchId);
    }

    function test_NonAdminCantSweepUnclaimed() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);
        vm.warp(block.timestamp + 30 days + 1);

        vm.prank(alice);
        vm.expectRevert();
        betting.sweepUnclaimed(matchId, alice);
    }

    // ─── Edge Cases ───

    function test_DoubleBetReverts() public {
        _createMatch();
        vm.prank(alice);
        betting.placeBet{value: 1 ether}(matchId, 0);

        vm.prank(alice);
        vm.expectRevert(RawlBetting.AlreadyBet.selector);
        betting.placeBet{value: 1 ether}(matchId, 1);
    }

    function test_BetAfterLockReverts() public {
        _createMatch();
        vm.prank(oracle);
        betting.lockMatch(matchId);

        vm.prank(alice);
        vm.expectRevert(RawlBetting.MatchNotOpen.selector);
        betting.placeBet{value: 1 ether}(matchId, 0);
    }

    function test_BetAfterWindowReverts() public {
        vm.prank(oracle);
        betting.createMatch(matchId, makeAddr("a"), makeAddr("b"), 0, 60); // 60s window

        vm.warp(block.timestamp + 61);

        vm.prank(alice);
        vm.expectRevert(RawlBetting.BettingWindowClosed.selector);
        betting.placeBet{value: 1 ether}(matchId, 0);
    }

    function test_ClaimWrongSideReverts() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0); // Side A wins

        vm.prank(bob); // Bob bet on Side B
        vm.expectRevert(RawlBetting.BetOnLosingSide.selector);
        betting.claimPayout(matchId);
    }

    function test_ClaimTwiceReverts() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);

        vm.prank(alice);
        betting.claimPayout(matchId);

        vm.prank(alice);
        vm.expectRevert(RawlBetting.AlreadyClaimed.selector);
        betting.claimPayout(matchId);
    }

    function test_ZeroBetReverts() public {
        _createMatch();
        vm.prank(alice);
        vm.expectRevert(RawlBetting.ZeroBetAmount.selector);
        betting.placeBet{value: 0}(matchId, 0);
    }

    function test_BetBelowMinReverts() public {
        _createMatch(); // minBet = 0.001 ether
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(RawlBetting.BetBelowMinimum.selector, 0.001 ether));
        betting.placeBet{value: 0.0001 ether}(matchId, 0);
    }

    function test_InvalidSideReverts() public {
        _createMatch();
        vm.prank(alice);
        vm.expectRevert(RawlBetting.InvalidSide.selector);
        betting.placeBet{value: 1 ether}(matchId, 2);
    }

    // ─── Config ───

    function test_UpdateConfig() public {
        vm.prank(admin);
        betting.updateConfig(500, 3600, address(0)); // feeBps=5%, timeout=1h, skip treasury

        assertEq(betting.feeBps(), 500);
        assertEq(betting.matchTimeout(), 3600);
        assertEq(betting.treasury(), treasury); // unchanged
    }

    function test_UpdateConfigFeeTooHighReverts() public {
        vm.prank(admin);
        vm.expectRevert(RawlBetting.InvalidFeeBps.selector);
        betting.updateConfig(1001, 0, address(0));
    }

    // ─── Pause ───

    function test_PauseBlocksCreateAndBet() public {
        vm.prank(admin);
        betting.pause();

        vm.prank(oracle);
        vm.expectRevert();
        betting.createMatch(matchId, makeAddr("a"), makeAddr("b"), 0, 0);
    }

    function test_PauseDoesNotBlockClaims() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);

        vm.prank(admin);
        betting.pause();

        // Claims still work when paused
        vm.prank(alice);
        betting.claimPayout(matchId);
    }

    function test_PauseDoesNotBlockRefunds() public {
        _createAndBetBothSides();
        vm.prank(admin);
        betting.cancelMatch(matchId);

        vm.prank(admin);
        betting.pause();

        // Refunds still work when paused
        vm.prank(alice);
        betting.refundBet(matchId);
    }

    // ─── Fee Snapshot Immutability ───

    function test_FeeSnapshotImmutable() public {
        _createMatch(); // feeBps=300 at creation

        // Change global fee
        vm.prank(admin);
        betting.updateConfig(500, 0, address(0));

        // Bet after fee change
        vm.prank(alice);
        betting.placeBet{value: 1 ether}(matchId, 0);
        vm.prank(bob);
        betting.placeBet{value: 1 ether}(matchId, 1);

        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);

        // Payout uses original 300 bps (3%), not new 500 bps
        uint256 aliceBefore = alice.balance;
        vm.prank(alice);
        betting.claimPayout(matchId);
        // totalPool=2, fee=2*300/10000=0.06, net=1.94, payout=1.94*1/1=1.94
        assertEq(alice.balance - aliceBefore, 1.94 ether);
    }

    // ─── Cancel from Locked State ───

    function test_CancelFromLockedState() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);

        // Admin can cancel even locked matches
        vm.prank(admin);
        betting.cancelMatch(matchId);

        vm.prank(alice);
        betting.refundBet(matchId);
    }

    // ─── WithdrawFees Guards ───

    function test_WithdrawFeesBlockedBeforeClaimWindow() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);
        vm.prank(alice);
        betting.claimPayout(matchId);

        vm.prank(admin);
        vm.expectRevert(RawlBetting.ClaimWindowNotElapsed.selector);
        betting.withdrawFees(matchId);
    }

    function test_WithdrawFeesBlockedWithRemainingWinners() public {
        _createAndBetBothSides();
        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);
        // Alice doesn't claim

        vm.warp(block.timestamp + 30 days + 1);

        vm.prank(admin);
        vm.expectRevert(RawlBetting.WinningBetsRemaining.selector);
        betting.withdrawFees(matchId);
    }

    // ─── Match Already Exists ───

    function test_CreateMatchTwiceReverts() public {
        _createMatch();
        vm.prank(oracle);
        vm.expectRevert(RawlBetting.MatchAlreadyExists.selector);
        betting.createMatch(matchId, makeAddr("a"), makeAddr("b"), 0, 0);
    }
}
