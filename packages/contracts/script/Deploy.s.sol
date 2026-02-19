// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/RawlBetting.sol";

contract DeployScript is Script {
    function run() public {
        address admin = vm.envAddress("ADMIN_ADDRESS");
        address oracle = vm.envAddress("ORACLE_ADDRESS");
        address treasury = vm.envAddress("TREASURY_ADDRESS");

        vm.startBroadcast();
        RawlBetting betting = new RawlBetting(admin, oracle, treasury);
        vm.stopBroadcast();

        console.log("RawlBetting deployed to:", address(betting));
        console.log("  Admin:", admin);
        console.log("  Oracle:", oracle);
        console.log("  Treasury:", treasury);
    }
}
