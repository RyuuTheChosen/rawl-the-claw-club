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

export function LandingHowItWorks() {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-12 sm:py-16">
      <motion.h2
        className="mb-6 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        HOW IT WORKS
      </motion.h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 sm:gap-5">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.15, duration: 0.4 }}
          >
            <ArcadeCard glowColor={step.glow} hover className="relative h-full text-center px-3 py-5">
              <span className="absolute top-2 left-2 font-mono text-[10px] text-muted-foreground/40">
                {i + 1}
              </span>
              <step.icon className={`mx-auto mb-2.5 h-7 w-7 ${step.iconColor}`} />
              <h3 className="mb-1 font-pixel text-[9px] sm:text-[10px]">{step.title}</h3>
              <p className="text-[11px] leading-relaxed text-muted-foreground">{step.desc}</p>
            </ArcadeCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
