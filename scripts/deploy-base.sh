#!/usr/bin/env bash
# Deploy RawlBetting contract to Base Sepolia
# Usage: ./scripts/deploy-base.sh
#
# Required env vars:
#   BASE_SEPOLIA_RPC  — RPC URL for Base Sepolia
#   BASESCAN_API_KEY  — BaseScan API key for verification
#   DEPLOYER_ADDRESS  — Address of deployer account (already in forge keystore)
#   ADMIN_ADDRESS     — Address for ADMIN_ROLE
#   ORACLE_ADDRESS    — Address for ORACLE_ROLE
#   TREASURY_ADDRESS  — Address for fee treasury
set -euo pipefail

cd "$(dirname "$0")/../packages/contracts"

echo "=== Building contracts ==="
forge build --sizes

echo "=== Running tests ==="
forge test -vvv

echo "=== Deploying to Base Sepolia ==="
forge script script/Deploy.s.sol \
  --rpc-url "$BASE_SEPOLIA_RPC" \
  --account deployer \
  --broadcast \
  --verify \
  --etherscan-api-key "$BASESCAN_API_KEY"

echo "=== Done ==="
echo "Check deploy artifacts in packages/contracts/broadcast/"
