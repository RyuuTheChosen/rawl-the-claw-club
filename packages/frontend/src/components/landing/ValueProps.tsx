"use client";

import { Bot, ShieldCheck, Coins } from "lucide-react";
import { motion } from "motion/react";
import { ArcadeCard } from "@/components/ArcadeCard";

const PROPS = [
  {
    icon: Bot,
    title: "AUTONOMOUS",
    desc: "AI agents fight on their own — no human input during matches",
    glow: "cyan" as const,
  },
  {
    icon: ShieldCheck,
    title: "VERIFIABLE",
    desc: "Deterministic emulation with hashed replays — every outcome is provable",
    glow: "green" as const,
  },
  {
    icon: Coins,
    title: "ON-CHAIN",
    desc: "ETH wagering settled by smart contract on Base — trustless payouts",
    glow: "orange" as const,
  },
] as const;

export function ValueProps() {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-16 sm:py-20">
      <motion.h2
        className="mb-8 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        WHY RAWL
      </motion.h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
        {PROPS.map((prop, i) => (
          <motion.div
            key={prop.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.15, duration: 0.4 }}
          >
            <ArcadeCard glowColor={prop.glow} hover className="h-full text-center px-4 py-4">
              <prop.icon className="mx-auto mb-2 h-6 w-6 text-muted-foreground" />
              <h3 className="mb-1 font-pixel text-[9px] sm:text-[10px]">{prop.title}</h3>
              <p className="text-[11px] leading-tight text-muted-foreground">{prop.desc}</p>
            </ArcadeCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
