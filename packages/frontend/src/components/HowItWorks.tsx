"use client";

import { Cpu, Upload, Swords, Coins } from "lucide-react";
import { motion } from "motion/react";
import { ArcadeCard } from "@/components/ArcadeCard";

const STEPS = [
  { icon: Cpu, title: "TRAIN", desc: "Train AI fighters with reinforcement learning on your GPU", glow: "cyan" as const },
  { icon: Upload, title: "DEPLOY", desc: "Upload your trained model and deploy it to the arena", glow: "green" as const },
  { icon: Swords, title: "COMPETE", desc: "Enter ranked matches, climb the leaderboard", glow: "pink" as const },
  { icon: Coins, title: "EARN", desc: "Bet SOL on match outcomes and claim payouts on-chain", glow: "orange" as const },
] as const;

export function HowItWorks() {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 py-12">
      <motion.h2
        className="mb-8 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        HOW IT WORKS
      </motion.h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 sm:gap-6">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.15, duration: 0.4 }}
          >
            <ArcadeCard glowColor={step.glow} hover className="relative text-center">
              <span className="absolute top-2 left-2 font-mono text-xs text-muted-foreground/40">
                {i + 1}
              </span>
              <step.icon className="mx-auto mb-3 h-7 w-7 text-muted-foreground" />
              <h3 className="mb-1 font-pixel text-[10px]">{step.title}</h3>
              <p className="text-xs text-muted-foreground">{step.desc}</p>
            </ArcadeCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
