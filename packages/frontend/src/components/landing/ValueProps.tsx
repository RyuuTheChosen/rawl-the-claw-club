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

export function ValueProps() {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-12 sm:py-16">
      <motion.h2
        className="mb-6 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        WHY RAWL
      </motion.h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-5">
        {PROPS.map((prop, i) => (
          <motion.div
            key={prop.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.15, duration: 0.4 }}
          >
            <ArcadeCard glowColor={prop.glow} hover className="h-full text-center px-5 py-6">
              <prop.icon className={`mx-auto mb-3 h-8 w-8 ${prop.iconColor}`} />
              <h3 className="mb-1.5 font-pixel text-[10px] sm:text-[11px]">{prop.title}</h3>
              <p className="text-xs leading-relaxed text-muted-foreground">{prop.desc}</p>
            </ArcadeCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
