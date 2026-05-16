const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AuditAnchor", function () {
  let anchor, owner, writer, attacker;

  beforeEach(async function () {
    [owner, writer, attacker] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("AuditAnchor");
    anchor = await Factory.deploy();
    await anchor.waitForDeployment();
    await anchor.addWriter(writer.address);
  });

  it("commits the first anchor and returns it", async function () {
    const chainHash = ethers.keccak256(ethers.toUtf8Bytes("genesis-chain-tip"));
    const payloadRoot = ethers.keccak256(ethers.toUtf8Bytes("merkle-root-1"));
    await expect(anchor.connect(writer).commitAnchor(1, 100, chainHash, payloadRoot))
      .to.emit(anchor, "AnchorCommitted")
      .withArgs(0, 1, 100, chainHash, payloadRoot, writer.address);

    const a = await anchor.latestAnchor();
    expect(a.indexInLedger).to.equal(100);
    expect(a.fromBlockId).to.equal(1);
    expect(a.chainHash).to.equal(chainHash);
    expect(a.submitter).to.equal(writer.address);
  });

  it("rejects non-contiguous ranges", async function () {
    const h = ethers.keccak256(ethers.toUtf8Bytes("h1"));
    await anchor.connect(writer).commitAnchor(1, 10, h, ethers.ZeroHash);
    await expect(
      anchor.connect(writer).commitAnchor(20, 30, h, ethers.ZeroHash)
    ).to.be.revertedWith("AuditAnchor: non-contiguous fromBlockId");
  });

  it("rejects empty chainHash", async function () {
    await expect(
      anchor.connect(writer).commitAnchor(1, 5, ethers.ZeroHash, ethers.ZeroHash)
    ).to.be.revertedWith("AuditAnchor: empty chainHash");
  });

  it("rejects writes from non-writers", async function () {
    const h = ethers.keccak256(ethers.toUtf8Bytes("h"));
    await expect(
      anchor.connect(attacker).commitAnchor(1, 5, h, ethers.ZeroHash)
    ).to.be.revertedWith("AuditAnchor: not writer");
  });

  it("verify() returns true only for matching hash", async function () {
    const h = ethers.keccak256(ethers.toUtf8Bytes("real-hash"));
    const wrong = ethers.keccak256(ethers.toUtf8Bytes("wrong-hash"));
    await anchor.connect(writer).commitAnchor(1, 50, h, ethers.ZeroHash);
    expect(await anchor.verify(0, h)).to.equal(true);
    expect(await anchor.verify(0, wrong)).to.equal(false);
    expect(await anchor.verify(99, h)).to.equal(false);
  });

  it("owner can rotate writers but cannot mutate history", async function () {
    const h = ethers.keccak256(ethers.toUtf8Bytes("immutable"));
    await anchor.connect(writer).commitAnchor(1, 5, h, ethers.ZeroHash);
    await anchor.removeWriter(writer.address);
    await expect(
      anchor.connect(writer).commitAnchor(6, 10, h, ethers.ZeroHash)
    ).to.be.revertedWith("AuditAnchor: not writer");

    // Existing record still readable and unchanged.
    const a = await anchor.getAnchor(0);
    expect(a.chainHash).to.equal(h);
  });
});
