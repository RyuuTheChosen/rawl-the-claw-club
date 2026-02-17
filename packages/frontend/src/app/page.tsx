"use client";

import Link from "next/link";
import { Eye, Cpu, Swords } from "lucide-react";
import { motion } from "motion/react";
import { ArcadeCard } from "@/components/ArcadeCard";
import { ArcadeButton } from "@/components/ArcadeButton";
import { VsScreen } from "@/components/VsScreen";
import { PageTransition } from "@/components/PageTransition";

const features = [
  {
    icon: Eye,
    title: "SPECTATE",
    description: "Watch AI fighters clash in real-time with live WebSocket streaming",
    glow: "cyan" as const,
    color: "text-neon-cyan",
  },
  {
    icon: Cpu,
    title: "TRAIN",
    description: "Train your own AI fighter using reinforcement learning on your GPU",
    glow: "green" as const,
    color: "text-neon-green",
  },
  {
    icon: Swords,
    title: "COMPETE",
    description: "Enter the ranked ladder, climb the leaderboard, and bet on outcomes",
    glow: "pink" as const,
    color: "text-neon-pink",
  },
];

export default function Home() {
  return (
    <PageTransition>
      <div className="flex flex-col items-center">
        {/* Hero */}
        <section className="flex flex-col items-center px-4 pt-16 pb-12 text-center sm:pt-24">
          <motion.h1
            className="font-pixel text-3xl text-neon-orange text-glow-orange sm:text-5xl"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            RAWL
          </motion.h1>
          <motion.p
            className="mt-3 font-pixel text-[10px] tracking-[0.2em] text-muted-foreground sm:text-xs"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            AI FIGHTING GAME ARENA
          </motion.p>

          <VsScreen fighterA="PLAYER 1" fighterB="PLAYER 2" />

          <motion.div
            className="mt-6 flex gap-3"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.4 }}
          >
            <Link href="/lobby">
              <ArcadeButton variant="primary" size="lg" glow>
                Enter Lobby
              </ArcadeButton>
            </Link>
            <Link href="/leaderboard">
              <ArcadeButton variant="outline" size="lg">
                High Scores
              </ArcadeButton>
            </Link>
          </motion.div>
        </section>

        {/* Features */}
        <section className="mx-auto grid w-full max-w-4xl gap-6 px-4 pb-16 sm:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 + i * 0.15, duration: 0.4 }}
            >
              <ArcadeCard glowColor={f.glow} hover={false} className="text-center">
                <f.icon className={`mx-auto mb-3 h-8 w-8 ${f.color}`} />
                <h2 className="mb-2 font-pixel text-xs">{f.title}</h2>
                <p className="text-sm text-muted-foreground">{f.description}</p>
              </ArcadeCard>
            </motion.div>
          ))}
        </section>

        {/* Stats bar */}
        <section className="w-full border-t border-border bg-card/50 py-6">
          <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-8 px-4">
            {[
              { label: "MATCHES", value: "--" },
              { label: "FIGHTERS", value: "--" },
              { label: "POOL VOL", value: "-- SOL" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="font-mono text-lg text-neon-orange">
                  {stat.value}
                </div>
                <div className="font-pixel text-[8px] text-muted-foreground">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </PageTransition>
  );
}
