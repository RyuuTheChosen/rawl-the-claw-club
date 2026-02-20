"use client";

import { motion } from "motion/react";
import { ArcadeCard } from "@/components/ArcadeCard";

const GAMES: { name: string; full: string; glow: "cyan" | "pink" | "green" | "orange"; primary?: boolean }[] = [
  { name: "SF2 CE", full: "Street Fighter II Champion Edition", glow: "cyan", primary: true },
  { name: "SF3 3S", full: "Street Fighter III: 3rd Strike", glow: "pink" },
  { name: "KOF 98", full: "King of Fighters '98", glow: "green" },
  { name: "TEKKEN TAG", full: "Tekken Tag Tournament", glow: "orange" },
];

export function LandingGames() {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-12 sm:py-16">
      <motion.h2
        className="mb-6 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        LAUNCH TITLES
      </motion.h2>
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
              className={`h-full text-center px-3 py-5 ${game.primary ? "ring-1 ring-neon-cyan/30" : "opacity-40"}`}
            >
              <h3 className="font-pixel text-[10px] sm:text-[11px]">{game.name}</h3>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{game.full}</p>
              <span className={`mt-2 inline-block font-pixel text-[8px] uppercase tracking-wider ${game.primary ? "text-neon-cyan" : "text-muted-foreground/50"}`}>
                Coming Soon
              </span>
            </ArcadeCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
