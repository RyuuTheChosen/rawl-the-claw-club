"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArcadeCard } from "@/components/ArcadeCard";
import type { GameId } from "@/types";

interface GameInfo {
  id: GameId;
  name: string;
  full: string;
  glow: "cyan" | "pink" | "green" | "orange";
}

const GAMES: (GameInfo & { soon?: boolean })[] = [
  { id: "sf2ce", name: "SF2 CE", full: "Street Fighter II Champion Edition", glow: "cyan" },
  { id: "sfiii3n", name: "SF3 3S", full: "Street Fighter III: 3rd Strike", glow: "pink", soon: true },
  { id: "kof98", name: "KOF 98", full: "King of Fighters '98", glow: "green", soon: true },
  { id: "tektagt", name: "TEKKEN TAG", full: "Tekken Tag Tournament", glow: "orange", soon: true },
];

export function GamesShowcase() {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-10">
      <motion.h2
        className="mb-8 text-center font-pixel text-xs tracking-widest text-muted-foreground sm:text-sm"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        GAMES
      </motion.h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        {GAMES.map((game, i) => (
          <motion.div
            key={game.id}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1, duration: 0.4 }}
            className="h-full"
          >
            {game.soon ? (
              <ArcadeCard glowColor={game.glow} hover={false} className="h-full text-center px-3 py-3 opacity-50">
                <h3 className="font-pixel text-[9px] sm:text-[10px]">{game.name}</h3>
                <p className="mt-0.5 text-[11px] leading-tight text-muted-foreground">{game.full}</p>
                <span className="mt-1 inline-block font-pixel text-[8px] uppercase tracking-wider text-muted-foreground/60">Soon</span>
              </ArcadeCard>
            ) : (
              <Link href={`/lobby?game=${game.id}`} className="block h-full">
                <ArcadeCard glowColor={game.glow} hover className="h-full text-center px-3 py-3">
                  <h3 className="font-pixel text-[9px] sm:text-[10px]">{game.name}</h3>
                  <p className="mt-0.5 text-[11px] leading-tight text-muted-foreground">{game.full}</p>
                </ArcadeCard>
              </Link>
            )}
          </motion.div>
        ))}
      </div>
    </section>
  );
}
