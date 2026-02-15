import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Rawl } from "../target/types/rawl";
import { expect } from "chai";
import { Keypair, SystemProgram, PublicKey, LAMPORTS_PER_SOL } from "@solana/web3.js";

describe("rawl", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.Rawl as Program<Rawl>;
  const authority = provider.wallet;
  const oracle = Keypair.generate();
  const treasury = Keypair.generate();

  const [platformConfigPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("platform_config")],
    program.programId
  );

  const matchId = Buffer.alloc(32);
  matchId.write("test-match-001");

  const [matchPoolPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("match_pool"), matchId],
    program.programId
  );

  const [vaultPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("vault"), matchId],
    program.programId
  );

  const fighterA = Keypair.generate().publicKey;
  const fighterB = Keypair.generate().publicKey;
  const bettor = Keypair.generate();

  before(async () => {
    // Airdrop to bettor for betting tests
    const sig = await provider.connection.requestAirdrop(
      bettor.publicKey,
      2 * LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(sig);
  });

  // ---- Platform Config ----

  it("initializes platform config", async () => {
    await program.methods
      .initialize(300, new anchor.BN(1800))
      .accounts({
        platformConfig: platformConfigPda,
        authority: authority.publicKey,
        oracle: oracle.publicKey,
        treasury: treasury.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    const config = await program.account.platformConfig.fetch(platformConfigPda);
    expect(config.feeBps).to.equal(300);
    expect(config.matchTimeout.toNumber()).to.equal(1800);
    expect(config.paused).to.equal(false);
  });

  it("updates platform fee", async () => {
    await program.methods
      .updateFee(500)
      .accounts({
        platformConfig: platformConfigPda,
        authority: authority.publicKey,
      })
      .rpc();

    const config = await program.account.platformConfig.fetch(platformConfigPda);
    expect(config.feeBps).to.equal(500);

    // Reset to default
    await program.methods
      .updateFee(300)
      .accounts({
        platformConfig: platformConfigPda,
        authority: authority.publicKey,
      })
      .rpc();
  });

  it("rejects fee above maximum", async () => {
    try {
      await program.methods
        .updateFee(1100)
        .accounts({
          platformConfig: platformConfigPda,
          authority: authority.publicKey,
        })
        .rpc();
      expect.fail("Should have thrown");
    } catch (err: any) {
      expect(err.error.errorCode.code).to.equal("InvalidFeeBps");
    }
  });

  it("pauses and unpauses platform", async () => {
    await program.methods
      .pause()
      .accounts({
        platformConfig: platformConfigPda,
        authority: authority.publicKey,
      })
      .rpc();

    let config = await program.account.platformConfig.fetch(platformConfigPda);
    expect(config.paused).to.equal(true);

    await program.methods
      .unpause()
      .accounts({
        platformConfig: platformConfigPda,
        authority: authority.publicKey,
      })
      .rpc();

    config = await program.account.platformConfig.fetch(platformConfigPda);
    expect(config.paused).to.equal(false);
  });

  // ---- Match Lifecycle ----

  it("creates a match", async () => {
    await program.methods
      .createMatch([...matchId], fighterA, fighterB)
      .accounts({
        matchPool: matchPoolPda,
        vault: vaultPda,
        platformConfig: platformConfigPda,
        creator: authority.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    const pool = await program.account.matchPool.fetch(matchPoolPda);
    expect(pool.sideATotal.toNumber()).to.equal(0);
    expect(pool.sideBTotal.toNumber()).to.equal(0);
    expect(pool.betCount).to.equal(0);
    expect(pool.status).to.deep.equal({ open: {} });
    expect(pool.winner).to.deep.equal({ none: {} });
  });

  it("places a bet on side A", async () => {
    const betAmount = new anchor.BN(0.5 * LAMPORTS_PER_SOL);
    const [betPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("bet"), matchId, bettor.publicKey.toBuffer()],
      program.programId
    );

    await program.methods
      .placeBet([...matchId], 0, betAmount)
      .accounts({
        matchPool: matchPoolPda,
        bet: betPda,
        vault: vaultPda,
        bettor: bettor.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([bettor])
      .rpc();

    const pool = await program.account.matchPool.fetch(matchPoolPda);
    expect(pool.sideATotal.toNumber()).to.equal(0.5 * LAMPORTS_PER_SOL);
    expect(pool.sideABetCount).to.equal(1);
    expect(pool.betCount).to.equal(1);

    const bet = await program.account.bet.fetch(betPda);
    expect(bet.bettor.toBase58()).to.equal(bettor.publicKey.toBase58());
    expect(bet.amount.toNumber()).to.equal(0.5 * LAMPORTS_PER_SOL);
    expect(bet.claimed).to.equal(false);
  });

  it("rejects zero amount bet", async () => {
    const bettor2 = Keypair.generate();
    const sig = await provider.connection.requestAirdrop(
      bettor2.publicKey,
      LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(sig);

    const [betPda2] = PublicKey.findProgramAddressSync(
      [Buffer.from("bet"), matchId, bettor2.publicKey.toBuffer()],
      program.programId
    );

    try {
      await program.methods
        .placeBet([...matchId], 0, new anchor.BN(0))
        .accounts({
          matchPool: matchPoolPda,
          bet: betPda2,
          vault: vaultPda,
          bettor: bettor2.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .signers([bettor2])
        .rpc();
      expect.fail("Should have thrown");
    } catch (err: any) {
      expect(err.error.errorCode.code).to.equal("ZeroBetAmount");
    }
  });

  it("locks a match (oracle)", async () => {
    await program.methods
      .lockMatch([...matchId])
      .accounts({
        matchPool: matchPoolPda,
        oracle: oracle.publicKey,
        platformConfig: platformConfigPda,
      })
      .signers([oracle])
      .rpc();

    const pool = await program.account.matchPool.fetch(matchPoolPda);
    expect(pool.status).to.deep.equal({ locked: {} });
    expect(pool.lockTimestamp.toNumber()).to.be.greaterThan(0);
  });

  it("rejects bet on locked match", async () => {
    const bettor3 = Keypair.generate();
    const sig = await provider.connection.requestAirdrop(
      bettor3.publicKey,
      LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(sig);

    const [betPda3] = PublicKey.findProgramAddressSync(
      [Buffer.from("bet"), matchId, bettor3.publicKey.toBuffer()],
      program.programId
    );

    try {
      await program.methods
        .placeBet([...matchId], 1, new anchor.BN(0.1 * LAMPORTS_PER_SOL))
        .accounts({
          matchPool: matchPoolPda,
          bet: betPda3,
          vault: vaultPda,
          bettor: bettor3.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .signers([bettor3])
        .rpc();
      expect.fail("Should have thrown");
    } catch (err: any) {
      expect(err.error.errorCode.code).to.equal("MatchNotOpen");
    }
  });

  it("resolves a match (oracle)", async () => {
    await program.methods
      .resolveMatch([...matchId], 0) // side A wins
      .accounts({
        matchPool: matchPoolPda,
        oracle: oracle.publicKey,
        platformConfig: platformConfigPda,
      })
      .signers([oracle])
      .rpc();

    const pool = await program.account.matchPool.fetch(matchPoolPda);
    expect(pool.status).to.deep.equal({ resolved: {} });
    expect(pool.winner).to.deep.equal({ sideA: {} });
    expect(pool.resolveTimestamp.toNumber()).to.be.greaterThan(0);
  });

  it("claims a winning bet", async () => {
    const [betPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("bet"), matchId, bettor.publicKey.toBuffer()],
      program.programId
    );

    const balanceBefore = await provider.connection.getBalance(bettor.publicKey);

    await program.methods
      .claimBet([...matchId])
      .accounts({
        matchPool: matchPoolPda,
        bet: betPda,
        vault: vaultPda,
        bettor: bettor.publicKey,
        platformConfig: platformConfigPda,
        treasury: treasury.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([bettor])
      .rpc();

    const bet = await program.account.bet.fetch(betPda);
    expect(bet.claimed).to.equal(true);

    const balanceAfter = await provider.connection.getBalance(bettor.publicKey);
    expect(balanceAfter).to.be.greaterThan(balanceBefore);
  });

  it("rejects double claim", async () => {
    const [betPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("bet"), matchId, bettor.publicKey.toBuffer()],
      program.programId
    );

    try {
      await program.methods
        .claimBet([...matchId])
        .accounts({
          matchPool: matchPoolPda,
          bet: betPda,
          vault: vaultPda,
          bettor: bettor.publicKey,
          platformConfig: platformConfigPda,
          treasury: treasury.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .signers([bettor])
        .rpc();
      expect.fail("Should have thrown");
    } catch (err: any) {
      expect(err.error.errorCode.code).to.equal("AlreadyClaimed");
    }
  });

  // ---- Cancel Flow ----

  it("cancels a match and refunds", async () => {
    const matchId2 = Buffer.alloc(32);
    matchId2.write("test-match-cancel");

    const [matchPool2] = PublicKey.findProgramAddressSync(
      [Buffer.from("match_pool"), matchId2],
      program.programId
    );
    const [vault2] = PublicKey.findProgramAddressSync(
      [Buffer.from("vault"), matchId2],
      program.programId
    );

    // Create match
    await program.methods
      .createMatch([...matchId2], fighterA, fighterB)
      .accounts({
        matchPool: matchPool2,
        vault: vault2,
        platformConfig: platformConfigPda,
        creator: authority.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    // Place a bet
    const [betPda2] = PublicKey.findProgramAddressSync(
      [Buffer.from("bet"), matchId2, bettor.publicKey.toBuffer()],
      program.programId
    );
    await program.methods
      .placeBet([...matchId2], 0, new anchor.BN(0.1 * LAMPORTS_PER_SOL))
      .accounts({
        matchPool: matchPool2,
        bet: betPda2,
        vault: vault2,
        bettor: bettor.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([bettor])
      .rpc();

    // Cancel
    await program.methods
      .cancelMatch([...matchId2])
      .accounts({
        matchPool: matchPool2,
        oracle: oracle.publicKey,
        platformConfig: platformConfigPda,
      })
      .signers([oracle])
      .rpc();

    const pool = await program.account.matchPool.fetch(matchPool2);
    expect(pool.status).to.deep.equal({ cancelled: {} });

    // Refund
    const balanceBefore = await provider.connection.getBalance(bettor.publicKey);
    await program.methods
      .refundBet([...matchId2])
      .accounts({
        matchPool: matchPool2,
        bet: betPda2,
        vault: vault2,
        bettor: bettor.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([bettor])
      .rpc();

    const balanceAfter = await provider.connection.getBalance(bettor.publicKey);
    expect(balanceAfter).to.be.greaterThan(balanceBefore);
  });

  // ---- Authorization Tests ----

  it("rejects non-oracle lock", async () => {
    const matchId3 = Buffer.alloc(32);
    matchId3.write("test-match-auth");

    const [matchPool3] = PublicKey.findProgramAddressSync(
      [Buffer.from("match_pool"), matchId3],
      program.programId
    );
    const [vault3] = PublicKey.findProgramAddressSync(
      [Buffer.from("vault"), matchId3],
      program.programId
    );

    await program.methods
      .createMatch([...matchId3], fighterA, fighterB)
      .accounts({
        matchPool: matchPool3,
        vault: vault3,
        platformConfig: platformConfigPda,
        creator: authority.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    const fakeOracle = Keypair.generate();
    try {
      await program.methods
        .lockMatch([...matchId3])
        .accounts({
          matchPool: matchPool3,
          oracle: fakeOracle.publicKey,
          platformConfig: platformConfigPda,
        })
        .signers([fakeOracle])
        .rpc();
      expect.fail("Should have thrown");
    } catch (err: any) {
      expect(err.error.errorCode.code).to.equal("OracleUnauthorized");
    }
  });

  it("rejects non-authority config updates", async () => {
    const fakeAuthority = Keypair.generate();
    try {
      await program.methods
        .updateFee(100)
        .accounts({
          platformConfig: platformConfigPda,
          authority: fakeAuthority.publicKey,
        })
        .signers([fakeAuthority])
        .rpc();
      expect.fail("Should have thrown");
    } catch (err: any) {
      expect(err.error.errorCode.code).to.equal("Unauthorized");
    }
  });
});
