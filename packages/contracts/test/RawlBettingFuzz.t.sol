// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/RawlBetting.sol";

contract RawlBettingFuzzTest is Test {
    RawlBetting public betting;

    address admin = makeAddr("admin");
    address oracle = makeAddr("oracle");
    address treasury = makeAddr("treasury");

    bytes32 matchId = keccak256("fuzz-match");

    function setUp() public {
        betting = new RawlBetting(admin, oracle, treasury);
    }

    function testFuzz_PayoutNeverExceedsPool(
        uint128 betA1,
        uint128 betA2,
        uint128 betB1
    ) public {
        betA1 = uint128(bound(betA1, 0.001 ether, 1000 ether));
        betA2 = uint128(bound(betA2, 0.001 ether, 1000 ether));
        betB1 = uint128(bound(betB1, 0.001 ether, 1000 ether));

        address a1 = makeAddr("a1");
        address a2 = makeAddr("a2");
        address b1 = makeAddr("b1");
        vm.deal(a1, uint256(betA1));
        vm.deal(a2, uint256(betA2));
        vm.deal(b1, uint256(betB1));

        vm.prank(oracle);
        betting.createMatch(matchId, makeAddr("fA"), makeAddr("fB"), 0.001 ether, 0);

        vm.prank(a1);
        betting.placeBet{value: betA1}(matchId, 0);
        vm.prank(a2);
        betting.placeBet{value: betA2}(matchId, 0);
        vm.prank(b1);
        betting.placeBet{value: betB1}(matchId, 1);

        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0); // Side A wins

        uint256 balanceBefore = address(betting).balance;

        vm.prank(a1);
        betting.claimPayout(matchId);
        vm.prank(a2);
        betting.claimPayout(matchId);

        // Contract balance after claims should be >= calculated fee
        uint256 totalPool = uint256(betA1) + uint256(betA2) + uint256(betB1);
        uint256 expectedFee = (totalPool * 300) / 10_000;
        // Allow 1 wei rounding tolerance
        assertGe(address(betting).balance + 1, expectedFee);
    }

    function testFuzz_RefundNoWinnersPreservesFees(uint128 bet1, uint128 bet2) public {
        bet1 = uint128(bound(bet1, 0.001 ether, 1000 ether));
        bet2 = uint128(bound(bet2, 0.001 ether, 1000 ether));

        address p1 = makeAddr("p1");
        address p2 = makeAddr("p2");
        vm.deal(p1, uint256(bet1));
        vm.deal(p2, uint256(bet2));

        vm.prank(oracle);
        betting.createMatch(matchId, makeAddr("fA"), makeAddr("fB"), 0.001 ether, 0);

        // Both bet on Side A
        vm.prank(p1);
        betting.placeBet{value: bet1}(matchId, 0);
        vm.prank(p2);
        betting.placeBet{value: bet2}(matchId, 0);

        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 1); // Side B wins (no bets on B)

        // Both refund with fee deducted
        vm.prank(p1);
        betting.refundNoWinners(matchId);
        vm.prank(p2);
        betting.refundNoWinners(matchId);

        // Contract should hold the fees
        uint256 totalPool = uint256(bet1) + uint256(bet2);
        uint256 expectedFee = totalPool - (uint256(bet1) * 9700 / 10_000) - (uint256(bet2) * 9700 / 10_000);
        assertGe(address(betting).balance + 1, expectedFee);
    }

    function testFuzz_OnePlayerPool(uint128 amount) public {
        amount = uint128(bound(amount, 0.001 ether, 1000 ether));

        address player = makeAddr("player");
        vm.deal(player, uint256(amount));

        vm.prank(oracle);
        betting.createMatch(matchId, makeAddr("fA"), makeAddr("fB"), 0.001 ether, 0);

        vm.prank(player);
        betting.placeBet{value: amount}(matchId, 0);

        vm.prank(oracle);
        betting.lockMatch(matchId);
        vm.prank(oracle);
        betting.resolveMatch(matchId, 0);

        uint256 playerBefore = player.balance;
        vm.prank(player);
        betting.claimPayout(matchId);

        // Contract math: fee = floor(amount * 300 / 10000), payout = amount - fee
        uint256 fee = (uint256(amount) * 300) / 10_000;
        uint256 expectedPayout = uint256(amount) - fee;
        assertEq(player.balance - playerBefore, expectedPayout);
    }

    function testFuzz_CancelFullRefund(uint128 betAmount) public {
        betAmount = uint128(bound(betAmount, 0.001 ether, 1000 ether));

        address player = makeAddr("player");
        vm.deal(player, uint256(betAmount));

        vm.prank(oracle);
        betting.createMatch(matchId, makeAddr("fA"), makeAddr("fB"), 0.001 ether, 0);

        vm.prank(player);
        betting.placeBet{value: betAmount}(matchId, 0);

        vm.prank(admin);
        betting.cancelMatch(matchId);

        uint256 playerBefore = player.balance;
        vm.prank(player);
        betting.refundBet(matchId);

        // Full refund — no fee on cancel
        assertEq(player.balance - playerBefore, uint256(betAmount));
    }
}
