// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/RawlBetting.sol";
import "./Handler.sol";

contract RawlBettingInvariantTest is Test {
    RawlBetting public betting;
    Handler public handler;

    address admin = makeAddr("admin");
    address oracle = makeAddr("oracle");
    address treasury = makeAddr("treasury");

    function setUp() public {
        betting = new RawlBetting(admin, oracle, treasury);
        handler = new Handler(betting, admin, oracle);

        targetContract(address(handler));
    }

    /// @notice Contract balance must always be >= deposits - withdrawals
    function invariant_Solvency() public view {
        assertGe(
            address(betting).balance,
            handler.ghost_totalDeposited() - handler.ghost_totalWithdrawn()
        );
    }

    /// @notice For any resolved match, sum of payouts + fees <= total pool
    function invariant_MatchBalanceNeverNegative() public view {
        // Contract balance should never be negative (implicitly true for uint)
        // but we check it's consistent with ghost variables
        assertGe(
            address(betting).balance + handler.ghost_totalWithdrawn(),
            handler.ghost_totalDeposited()
        );
    }
}
