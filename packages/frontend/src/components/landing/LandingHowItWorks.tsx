"use client";

import { Cpu, Upload, Swords, Coins } from "lucide-react";
import { motion } from "motion/react";
import { ArcadeCard } from "@/components/ArcadeCard";

const STEPS = [
  {
    icon: Cpu,
    title: "TRAIN",
    desc: "Train AI fighters with reinforcement learning on your GPU",
    glow: "cyan" as const,
  },
  {
    icon: Upload,
    title: "DEPLOY",
    desc: "Upload your trained model and deploy it to the arena",
    glow: "green" as const,
  },
  {
    icon: Swords,
    title: "COMPETE",
    desc: "Enter ranked matches and climb the leaderboard",
    glow: "pink" as const,
  },
  {
    icon: Coins,
    title: "EARN",
    desc: "Bet ETH on match outcomes and claim payouts on-chain",
    glow: "orange" as const,
  },
] as const;

export function LandingHowItWorks() {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-16 sm:py-20">
      <motion.h2
        className="mb-8 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        HOW IT WORKS
      </motion.h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.15, duration: 0.4 }}
          >
            <ArcadeCard glowColor={step.glow} hover className="relative h-full text-center px-3 py-3">
              <span className="absolute top-1.5 left-1.5 font-mono text-[10px] text-muted-foreground/40">
                {i + 1}
              </span>
              <step.icon className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
              <h3 className="mb-0.5 font-pixel text-[9px]">{step.title}</h3>
              <p className="text-[11px] leading-tight text-muted-foreground">{step.desc}</p>
            </ArcadeCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
