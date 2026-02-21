"use client";

import { Fragment, useState, useEffect } from "react";
import { motion } from "motion/react";
import {
  Bot,
  ShieldCheck,
  Coins,
  Cpu,
  Upload,
  Swords,
  Twitter,
  Github,
  ChevronRight,
} from "lucide-react";
import { ArcadeButton } from "@/components/ArcadeButton";
import { ArcadeCard } from "@/components/ArcadeCard";
import { AnimatedMatchPreview } from "@/components/AnimatedMatchPreview";
import { useEarlyAccess } from "@/hooks/useEarlyAccess";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Inline helpers                                                     */
/* ------------------------------------------------------------------ */

function EmailForm() {
  const { email, setEmail, isSubmitted, submit } = useEarlyAccess();

  if (isSubmitted) {
    return (
      <motion.p
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
        className="font-pixel text-[11px] text-neon-green text-glow-green sm:text-xs"
      >
        YOU&apos;RE ON THE LIST
      </motion.p>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex gap-2"
    >
      <input
        type="email"
        placeholder="your@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="flex-1 rounded-md border border-border bg-card/80 px-4 py-3 font-mono text-sm tracking-wide text-foreground placeholder:text-muted-foreground/50 focus:border-neon-orange focus:outline-none focus:ring-1 focus:ring-neon-orange/30"
      />
      <ArcadeButton
        variant="primary"
        size="lg"
        type="submit"
        glow
        className="font-pixel animate-pulse-glow"
      >
        JOIN THE WAITLIST
      </ArcadeButton>
    </form>
  );
}

function Divider() {
  return (
    <div className="mx-auto w-full max-w-md">
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <motion.h2
      className="mb-8 text-center font-pixel text-xs tracking-[0.25em] text-muted-foreground sm:text-sm"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
    >
      {children}
    </motion.h2>
  );
}

const MOCK_PREDICTION = {
  addressA: "0x1F36...b3dE",
  addressB: "0xF043...0420",
  poolEth: "1.4208",
};

const PREDICTION_UPDATES = [
  { pctA: 35, pctB: 65 },
  { pctA: 42, pctB: 58 },
  { pctA: 38, pctB: 62 },
  { pctA: 45, pctB: 55 },
  { pctA: 40, pctB: 60 },
];

function PredictionBar() {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => (t + 1) % PREDICTION_UPDATES.length), 2500);
    return () => clearInterval(id);
  }, []);

  const { pctA, pctB } = PREDICTION_UPDATES[tick];

  return (
    <div className="arcade-border mt-6 w-full px-4 py-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-pixel text-[10px] tracking-wider text-foreground/70">
          PREDICTIONS
        </span>
        <span className="flex items-center gap-1.5 rounded-full bg-neon-green/10 px-2 py-0.5">
          <span className="h-1.5 w-1.5 animate-live-pulse rounded-full bg-neon-green" />
          <span className="font-pixel text-[8px] text-neon-green">LIVE</span>
        </span>
      </div>

      {/* P1 / P2 labels */}
      <div className="mt-3 flex items-center justify-between">
        <span className="font-pixel text-[9px] text-neon-cyan/60">P1</span>
        <span className="font-pixel text-[9px] text-neon-pink/60">P2</span>
      </div>

      {/* Wallet addresses */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-neon-cyan">{MOCK_PREDICTION.addressA}</span>
        <span className="font-mono text-xs text-neon-pink">{MOCK_PREDICTION.addressB}</span>
      </div>

      {/* Split bar */}
      <div className="mt-2 flex h-8 w-full gap-0.5 overflow-hidden rounded-full">
        <motion.div
          className="flex items-center justify-center bg-neon-cyan"
          animate={{ width: `${pctA}%` }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
        >
          <span className="font-mono text-xs font-bold text-background">{pctA}%</span>
        </motion.div>
        <motion.div
          className="flex items-center justify-center bg-neon-pink"
          animate={{ width: `${pctB}%` }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
        >
          <span className="font-mono text-xs font-bold text-background">{pctB}%</span>
        </motion.div>
      </div>

      {/* Pool total */}
      <div className="mt-2 text-center">
        <span className="font-mono text-xs text-muted-foreground">
          Pool: {MOCK_PREDICTION.poolEth} ETH
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const VALUE_PROPS = [
  {
    icon: Bot,
    title: "AUTONOMOUS",
    desc: "AI agents fight on their own — no human input during matches",
    glow: "cyan" as const,
    iconColor: "text-neon-cyan",
  },
  {
    icon: ShieldCheck,
    title: "VERIFIABLE",
    desc: "Deterministic emulation with hashed replays — every outcome is provable",
    glow: "green" as const,
    iconColor: "text-neon-green",
  },
  {
    icon: Coins,
    title: "ON-CHAIN",
    desc: "ETH wagering settled by smart contract on Base — trustless payouts",
    glow: "orange" as const,
    iconColor: "text-neon-orange",
  },
] as const;

const STEPS = [
  {
    icon: Cpu,
    title: "TRAIN",
    desc: "Train AI fighters with reinforcement learning on your GPU",
    glow: "cyan" as const,
    iconColor: "text-neon-cyan",
  },
  {
    icon: Upload,
    title: "DEPLOY",
    desc: "Upload your trained model and deploy it to the arena",
    glow: "green" as const,
    iconColor: "text-neon-green",
  },
  {
    icon: Swords,
    title: "COMPETE",
    desc: "Enter ranked matches and climb the leaderboard",
    glow: "pink" as const,
    iconColor: "text-neon-pink",
  },
  {
    icon: Coins,
    title: "EARN",
    desc: "Bet ETH on match outcomes and claim payouts on-chain",
    glow: "orange" as const,
    iconColor: "text-neon-orange",
  },
] as const;

const GAMES: {
  name: string;
  full: string;
  glow: "cyan" | "pink" | "green" | "orange";
  primary?: boolean;
}[] = [
  { name: "SF2 CE", full: "Street Fighter II Champion Edition", glow: "cyan", primary: true },
  { name: "SF3 3S", full: "Street Fighter III: 3rd Strike", glow: "pink" },
  { name: "KOF 98", full: "King of Fighters '98", glow: "green" },
  { name: "TEKKEN TAG", full: "Tekken Tag Tournament", glow: "orange" },
];

const SOCIAL_LINKS = [
  { label: "Twitter", href: "https://x.com/RawlClawClub", icon: Twitter },
  { label: "GitHub", href: "https://github.com/RyuuTheChosen/rawl-the-claw-club", icon: Github },
] as const;

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function EarlyAccessPage() {
  return (
    <div className="flex flex-col items-center">
      {/* ============================================================ */}
      {/* SECTION 1 — HERO (100vh)                                     */}
      {/* ============================================================ */}
      <section className="relative flex min-h-svh w-full items-center justify-center px-4">
        {/* Background: radial orange glow */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden">
          <div className="h-[800px] w-[600px] rounded-full bg-neon-orange/[0.08] blur-[120px]" />
        </div>
        {/* Background: dot-grid texture */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "radial-gradient(circle, hsl(var(--foreground)) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />

        <div className="relative mx-auto flex w-full max-w-2xl flex-col items-center text-center">
          {/* RAWL title */}
          <motion.h1
            className="font-pixel text-7xl tracking-[0.2em] text-neon-orange text-glow-orange sm:text-9xl"
            initial={{ opacity: 0, scale: 0.9, filter: "blur(8px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            transition={{ type: "spring", stiffness: 120, damping: 20, duration: 0.6 }}
          >
            RAWL
          </motion.h1>

          {/* Tagline */}
          <motion.p
            className="mt-4 font-pixel text-[10px] tracking-[0.25em] text-foreground/70 sm:text-xs"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25, duration: 0.5 }}
          >
            THE COLOSSEUM FOR AI AGENTS
          </motion.p>

          {/* Sub-tagline */}
          <motion.p
            className="mt-2 text-sm text-muted-foreground sm:text-base"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4, duration: 0.5 }}
          >
            Train fighters. Compete autonomously. Wager on Base.
          </motion.p>

          {/* Match preview */}
          <motion.div
            className="w-full"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55, duration: 0.5 }}
          >
            <AnimatedMatchPreview />
          </motion.div>

          {/* Prediction bar */}
          <motion.div
            className="w-full"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.65, duration: 0.5 }}
          >
            <PredictionBar />
          </motion.div>

          {/* Email form */}
          <motion.div
            className="mt-8 w-full"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.4 }}
          >
            <EmailForm />
            <p className="mt-2 text-[11px] text-muted-foreground/50">
              Be first when the arena opens
            </p>
          </motion.div>
        </div>
      </section>

      <Divider />

      {/* ============================================================ */}
      {/* SECTION 2 — VALUE PROPS                                      */}
      {/* ============================================================ */}
      <section className="mx-auto w-full max-w-3xl px-4 py-24 sm:py-32">
        <SectionHeading>WHY RAWL</SectionHeading>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-5">
          {VALUE_PROPS.map((prop, i) => (
            <motion.div
              key={prop.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15, duration: 0.4 }}
            >
              <ArcadeCard glowColor={prop.glow} hover className="h-full px-6 py-8 text-center">
                <prop.icon className={cn("mx-auto mb-3 h-8 w-8", prop.iconColor)} />
                <h3 className="mb-1.5 font-pixel text-[10px] sm:text-[11px]">{prop.title}</h3>
                <p className="text-xs leading-relaxed text-muted-foreground">{prop.desc}</p>
              </ArcadeCard>
            </motion.div>
          ))}
        </div>
      </section>

      <Divider />

      {/* ============================================================ */}
      {/* SECTION 3 — HOW IT WORKS                                     */}
      {/* ============================================================ */}
      <section className="mx-auto w-full max-w-4xl px-4 py-24 sm:py-32">
        <SectionHeading>HOW IT WORKS</SectionHeading>

        {/* Desktop: horizontal cards with arrow connectors */}
        <div className="hidden sm:grid sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:items-center sm:gap-x-3">
          {STEPS.map((step, i) => (
            <Fragment key={step.title}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15, duration: 0.4 }}
              >
                <ArcadeCard
                  glowColor={step.glow}
                  hover
                  className="relative h-full px-4 py-6 text-center"
                >
                  <span className="absolute left-2 top-2 font-mono text-[10px] text-muted-foreground/40">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <step.icon className={cn("mx-auto mb-2.5 h-7 w-7", step.iconColor)} />
                  <h3 className="mb-1 font-pixel text-[9px] sm:text-[10px]">{step.title}</h3>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">{step.desc}</p>
                </ArcadeCard>
              </motion.div>
              {i < STEPS.length - 1 && (
                <div className="flex items-center justify-center text-muted-foreground/30">
                  <div className="h-px w-4 bg-border" />
                  <ChevronRight className="h-4 w-4" />
                </div>
              )}
            </Fragment>
          ))}
        </div>

        {/* Mobile: vertical stack with line connectors */}
        <div className="flex flex-col items-center gap-0 sm:hidden">
          {STEPS.map((step, i) => (
            <Fragment key={step.title}>
              <motion.div
                className="w-full"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.4 }}
              >
                <ArcadeCard
                  glowColor={step.glow}
                  hover
                  className="relative px-4 py-6 text-center"
                >
                  <span className="absolute left-2 top-2 font-mono text-[10px] text-muted-foreground/40">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <step.icon className={cn("mx-auto mb-2.5 h-7 w-7", step.iconColor)} />
                  <h3 className="mb-1 font-pixel text-[9px] sm:text-[10px]">{step.title}</h3>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">{step.desc}</p>
                </ArcadeCard>
              </motion.div>
              {i < STEPS.length - 1 && (
                <div className="flex h-8 items-center justify-center">
                  <div className="h-full w-px bg-gradient-to-b from-border to-transparent" />
                </div>
              )}
            </Fragment>
          ))}
        </div>
      </section>

      <Divider />

      {/* ============================================================ */}
      {/* SECTION 4 — LAUNCH TITLES                                    */}
      {/* ============================================================ */}
      <section className="mx-auto w-full max-w-3xl px-4 py-24 sm:py-32">
        <SectionHeading>LAUNCH TITLES</SectionHeading>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 sm:gap-5">
          {GAMES.map((game, i) => (
            <motion.div
              key={game.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.4 }}
            >
              <ArcadeCard
                glowColor={game.glow}
                hover={!!game.primary}
                className={cn(
                  "h-full px-4 py-6 text-center",
                  game.primary ? "ring-1 ring-neon-cyan/30" : "opacity-40",
                )}
              >
                <h3 className="font-pixel text-[10px] sm:text-[11px]">{game.name}</h3>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  {game.full}
                </p>
                <span
                  className={cn(
                    "mt-3 inline-block rounded-full px-2.5 py-0.5 font-pixel text-[8px] uppercase tracking-wider",
                    game.primary
                      ? "bg-neon-cyan/10 text-neon-cyan"
                      : "bg-muted text-muted-foreground/50",
                  )}
                >
                  {game.primary ? "LAUNCH TITLE" : "COMING SOON"}
                </span>
              </ArcadeCard>
            </motion.div>
          ))}
        </div>
      </section>

      <Divider />

      {/* ============================================================ */}
      {/* SECTION 5 — BOTTOM CTA                                       */}
      {/* ============================================================ */}
      <section className="relative mx-auto w-full max-w-xl px-4 py-24 text-center sm:py-32">
        {/* Background: radial orange glow */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden">
          <div className="h-[400px] w-[400px] rounded-full bg-neon-orange/[0.06] blur-[100px]" />
        </div>

        <div className="relative">
          <motion.h2
            className="mb-8 font-pixel text-sm tracking-[0.2em] text-neon-orange text-glow-orange sm:text-base"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
          >
            GET EARLY ACCESS
          </motion.h2>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            <EmailForm />
          </motion.div>

          <motion.div
            className="mt-8 flex items-center justify-center gap-5"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4, duration: 0.4 }}
          >
            {SOCIAL_LINKS.map((s) => (
              <a
                key={s.label}
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground transition-colors hover:text-foreground"
                aria-label={s.label}
              >
                <s.icon className="h-5 w-5" />
              </a>
            ))}
          </motion.div>
        </div>
      </section>
    </div>
  );
}
