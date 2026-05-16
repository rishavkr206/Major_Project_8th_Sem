/**
 * Deploy AuditAnchor and write the address to ../deployed.json so the
 * Python-side anchor service can pick it up automatically.
 */
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying AuditAnchor with account: ${deployer.address}`);
  console.log(`Network: ${network.name}`);

  const Factory = await ethers.getContractFactory("AuditAnchor");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`AuditAnchor deployed at: ${address}`);

  const out = {
    network: network.name,
    address,
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
  };
  const outPath = path.join(__dirname, "..", "deployed.json");
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  console.log(`Wrote deployment metadata to ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
