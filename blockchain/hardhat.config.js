/**
 * Hardhat config for the AuditAnchor on-chain commitment contract.
 *
 * Networks:
 *   - hardhat   : default in-process EVM, used by tests
 *   - localhost : `npx hardhat node` running on 127.0.0.1:8545
 *   - sepolia   : public testnet (env: SEPOLIA_RPC_URL, SEPOLIA_PRIVATE_KEY)
 *
 * Compile :  npx hardhat compile
 * Test    :  npx hardhat test
 * Deploy  :  npx hardhat run scripts/deploy.js --network localhost
 */

require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    hardhat: {},
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL || "",
      accounts: process.env.SEPOLIA_PRIVATE_KEY ? [process.env.SEPOLIA_PRIVATE_KEY] : [],
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
