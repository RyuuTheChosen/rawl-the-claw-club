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
/*  Email form                                                          */
/* ------------------------------------------------------------------ */

function EmailForm() {
  const { email, setEmail, isSubmitted, submit } = useEarlyAccess();

  if (isSubmitted) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
        className="flex items-center justify-center gap-2"
      >
        <div className="h-2 w-2 rounded-full bg-neon-green animate-live-pulse" />
        <p className="font-pixel text-[11px] text-neon-green text-glow-green sm:text-xs">
          YOU&apos;RE ON THE LIST
        </p>
      </motion.div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex w-full gap-2 sm:gap-3"
    >
      <input
        type="email"
        placeholder="your@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="flex-1 rounded-lg border border-border bg-card/80 px-4 py-3 font-mono text-sm tracking-wide text-foreground placeholder:text-muted-foreground/40 focus:border-neon-orange focus:outline-none focus:ring-1 focus:ring-neon-orange/30 transition-all duration-200"
      />
      <ArcadeButton
        variant="primary"
        size="lg"
        type="submit"
        glow
        className="font-pixel shrink-0 animate-pulse-glow"
      >
        JOIN WAITLIST
      </ArcadeButton>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/*  Section heading                                                     */
/* ------------------------------------------------------------------ */

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <motion.h2
      className="mb-10 text-center font-pixel text-xs tracking-[0.3em] text-muted-foreground sm:text-sm"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
    >
      {children}
    </motion.h2>
  );
}

/* ------------------------------------------------------------------ */
/*  Divider                                                             */
/* ------------------------------------------------------------------ */

function Divider() {
  return (
    <div className="mx-auto w-full max-w-md">
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Prediction bar                                                      */
/* ------------------------------------------------------------------ */

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
    const id = setInterval(
      () => setTick((t) => (t + 1) % PREDICTION_UPDATES.length),
      2500,
    );
    return () => clearInterval(id);
  }, []);

  const { pctA, pctB } = PREDICTION_UPDATES[tick];

  return (
    <div className="arcade-border w-full px-4 py-4">
      <div className="flex items-center justify-between">
        <span className="font-pixel text-[10px] tracking-wider text-foreground/70">
          PREDICTIONS
        </span>
        <span className="flex items-center gap-1.5 rounded-full bg-neon-green/10 px-2 py-0.5">
          <span className="h-1.5 w-1.5 animate-live-pulse rounded-full bg-neon-green" />
          <span className="font-pixel text-[8px] text-neon-green">LIVE</span>
        </span>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="font-pixel text-[9px] text-neon-cyan/60">P1</span>
        <span className="font-pixel text-[9px] text-neon-pink/60">P2</span>
      </div>

      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-neon-cyan">
          {MOCK_PREDICTION.addressA}
        </span>
        <span className="font-mono text-xs text-neon-pink">
          {MOCK_PREDICTION.addressB}
        </span>
      </div>

      <div className="mt-2 flex h-8 w-full gap-0.5 overflow-hidden rounded-full">
        <motion.div
          className="flex items-center justify-center bg-neon-cyan"
          animate={{ width: `${pctA}%` }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
        >
          <span className="font-mono text-xs font-bold text-background">
            {pctA}%
          </span>
        </motion.div>
        <motion.div
          className="flex items-center justify-center bg-neon-pink"
          animate={{ width: `${pctB}%` }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
        >
          <span className="font-mono text-xs font-bold text-background">
            {pctB}%
          </span>
        </motion.div>
      </div>

      <div className="mt-2 text-center">
        <span className="font-mono text-xs text-muted-foreground">
          Pool: {MOCK_PREDICTION.poolEth} ETH
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Data                                                                */
/* ------------------------------------------------------------------ */

const BADGES = [
  { label: "BASE L2", className: "text-neon-cyan border-neon-cyan/20 bg-neon-cyan/5" },
  { label: "OPEN SOURCE", className: "text-neon-green border-neon-green/20 bg-neon-green/5" },
  { label: "EARLY ACCESS", className: "text-neon-orange border-neon-orange/20 bg-neon-orange/5" },
];

const FEATURES = [
  {
    icon: Bot,
    title: "AUTONOMOUS FIGHTERS",
    desc: "AI agents fight on their own. No human input during matches — pure machine intelligence.",
    glow: "cyan" as const,
    iconColor: "text-neon-cyan",
  },
  {
    icon: ShieldCheck,
    title: "VERIFIABLE",
    desc: "Deterministic emulation with hashed replays. Every outcome is provable.",
    glow: "green" as const,
    iconColor: "text-neon-green",
  },
  {
    icon: Coins,
    title: "ON-CHAIN",
    desc: "ETH wagering settled by smart contract on Base. Trustless payouts.",
    glow: "orange" as const,
    iconColor: "text-neon-orange",
  },
] as const;

const STEPS = [
  {
    icon: Cpu,
    title: "TRAIN",
    desc: "Reinforcement learning on your GPU",
    glow: "cyan" as const,
    iconColor: "text-neon-cyan",
  },
  {
    icon: Upload,
    title: "DEPLOY",
    desc: "Upload your model to the arena",
    glow: "green" as const,
    iconColor: "text-neon-green",
  },
  {
    icon: Swords,
    title: "COMPETE",
    desc: "Ranked matches on the leaderboard",
    glow: "pink" as const,
    iconColor: "text-neon-pink",
  },
  {
    icon: Coins,
    title: "EARN",
    desc: "Bet ETH and claim payouts on-chain",
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
/*  Page                                                                */
/* ------------------------------------------------------------------ */

export default function EarlyAccessPage() {
  return (
    <div className="flex flex-col items-center overflow-x-hidden">
      {/* ============================================================ */}
      {/* SECTION 1 — HERO                                              */}
      {/* ============================================================ */}
      <section className="relative flex min-h-svh w-full items-start justify-center px-4 pt-20 sm:pt-28">
        {/* Background: multi-color gradient orbs */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-1/2 top-1/4 -translate-x-1/2 h-[600px] w-[500px] rounded-full bg-neon-orange/[0.07] blur-[140px]" />
          <div className="absolute -left-32 top-1/2 h-[400px] w-[400px] rounded-full bg-neon-cyan/[0.04] blur-[120px]" />
          <div className="absolute -right-32 top-1/3 h-[400px] w-[400px] rounded-full bg-neon-pink/[0.04] blur-[120px]" />
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
          {/* Badge pills */}
          <motion.div
            className="mb-6 flex flex-wrap items-center justify-center gap-2"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            {BADGES.map((badge) => (
              <span
                key={badge.label}
                className={cn(
                  "rounded-full border px-3 py-1 font-pixel text-[8px] tracking-wider",
                  badge.className,
                )}
              >
                {badge.label}
              </span>
            ))}
          </motion.div>

          {/* RAWL title */}
          <motion.h1
            className="font-pixel text-7xl tracking-[0.2em] pl-[0.2em] text-neon-orange text-glow-orange sm:text-9xl"
            initial={{ opacity: 0, scale: 0.9, filter: "blur(8px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            transition={{
              type: "spring",
              stiffness: 120,
              damping: 20,
              duration: 0.6,
            }}
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
            className="mt-6 w-full"
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

      {/* ============================================================ */}
      {/* SECTION 3 — FEATURES (Bento Grid)                             */}
      {/* ============================================================ */}
      <section className="mx-auto w-full max-w-3xl px-4 py-24 sm:py-32">
        <SectionHeading>WHY RAWL</SectionHeading>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
          {FEATURES.map((feat, i) => {
            const Icon = feat.icon;
            return (
              <motion.div
                key={feat.title}
                className={cn(i === 0 && "sm:row-span-2")}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15, duration: 0.4 }}
              >
                <ArcadeCard
                  glowColor={feat.glow}
                  hover
                  className={cn(
                    "h-full",
                    i === 0
                      ? "flex flex-col justify-between px-6 py-8"
                      : "px-6 py-6",
                  )}
                >
                  <div>
                    <Icon
                      className={cn(
                        i === 0 ? "mb-4 h-10 w-10" : "mb-3 h-8 w-8",
                        feat.iconColor,
                      )}
                    />
                    <h3
                      className={cn(
                        "font-pixel",
                        i === 0
                          ? "mb-2 text-[11px] sm:text-xs"
                          : "mb-1.5 text-[10px] sm:text-[11px]",
                      )}
                    >
                      {feat.title}
                    </h3>
                    <p
                      className={cn(
                        "leading-relaxed text-muted-foreground",
                        i === 0 ? "text-sm" : "text-xs",
                      )}
                    >
                      {feat.desc}
                    </p>
                  </div>
                  {i === 0 && (
                    <div className="mt-6 flex items-center gap-3">
                      <div className="h-px flex-1 bg-gradient-to-r from-neon-cyan/20 to-transparent" />
                      <span className="font-pixel text-[8px] text-neon-cyan/40">
                        AI vs AI
                      </span>
                    </div>
                  )}
                </ArcadeCard>
              </motion.div>
            );
          })}
        </div>
      </section>

      <Divider />

      {/* ============================================================ */}
      {/* SECTION 4 — HOW IT WORKS                                      */}
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
                  <step.icon
                    className={cn("mx-auto mb-2.5 h-7 w-7", step.iconColor)}
                  />
                  <h3 className="mb-1 font-pixel text-[9px] sm:text-[10px]">
                    {step.title}
                  </h3>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    {step.desc}
                  </p>
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
                  <step.icon
                    className={cn("mx-auto mb-2.5 h-7 w-7", step.iconColor)}
                  />
                  <h3 className="mb-1 font-pixel text-[9px] sm:text-[10px]">
                    {step.title}
                  </h3>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    {step.desc}
                  </p>
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
      {/* SECTION 5 — GAME ROSTER                                       */}
      {/* ============================================================ */}
      <section className="mx-auto w-full max-w-3xl px-4 py-24 sm:py-32">
        <SectionHeading>GAME ROSTER</SectionHeading>

        {/* Primary game: SF2 CE — hero card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          <ArcadeCard
            glowColor="cyan"
            hover
            className="mb-4 flex items-center justify-between px-6 py-8 ring-1 ring-neon-cyan/20 sm:mb-5"
          >
            <div>
              <span className="mb-2 inline-block rounded-full bg-neon-cyan/10 px-3 py-1 font-pixel text-[8px] tracking-wider text-neon-cyan">
                LAUNCH TITLE
              </span>
              <h3 className="font-pixel text-sm sm:text-base">SF2 CE</h3>
              <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
                Street Fighter II Champion Edition
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-neon-green animate-live-pulse" />
              <span className="font-pixel text-[9px] text-neon-green">ACTIVE</span>
            </div>
          </ArcadeCard>
        </motion.div>

        {/* Secondary games */}
        <div className="grid grid-cols-3 gap-4 sm:gap-5">
          {GAMES.filter((g) => !g.primary).map((game, i) => (
            <motion.div
              key={game.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.4 }}
            >
              <ArcadeCard
                glowColor={game.glow}
                hover={false}
                className="h-full px-3 py-5 text-center opacity-40 sm:px-4"
              >
                <h3 className="font-pixel text-[9px] sm:text-[10px]">
                  {game.name}
                </h3>
                <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground sm:text-[11px]">
                  {game.full}
                </p>
                <span className="mt-2 inline-block rounded-full bg-muted px-2 py-0.5 font-pixel text-[7px] uppercase tracking-wider text-muted-foreground/50 sm:text-[8px]">
                  COMING SOON
                </span>
              </ArcadeCard>
            </motion.div>
          ))}
        </div>
      </section>

      <Divider />

      {/* ============================================================ */}
      {/* SECTION 6 — BOTTOM CTA                                        */}
      {/* ============================================================ */}
      <section className="relative mx-auto w-full max-w-xl px-4 py-24 text-center sm:py-32">
        {/* Background glow */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden">
          <div className="h-[400px] w-[400px] rounded-full bg-neon-orange/[0.06] blur-[100px]" />
        </div>

        <div className="relative">
          <motion.h2
            className="mb-3 font-pixel text-sm tracking-[0.2em] text-neon-orange text-glow-orange sm:text-base"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
          >
            JOIN THE ARENA
          </motion.h2>

          <motion.p
            className="mb-8 text-sm text-muted-foreground"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15, duration: 0.4 }}
          >
            Be first when the arena opens
          </motion.p>

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
