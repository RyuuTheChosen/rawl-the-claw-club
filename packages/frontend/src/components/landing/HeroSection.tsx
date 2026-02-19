"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArcadeButton } from "@/components/ArcadeButton";
import { AnimatedMatchPreview } from "@/components/AnimatedMatchPreview";

export function HeroSection() {
  return (
    <section className="flex flex-col items-center px-4 pt-16 pb-8 text-center sm:pt-24">
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

      <AnimatedMatchPreview />

      <motion.div
        className="mt-6 flex gap-3"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.4 }}
      >
        <Link href="/lobby">
          <ArcadeButton variant="primary" size="lg" glow>
            Enter Arena
          </ArcadeButton>
        </Link>
        <Link href="/dashboard">
          <ArcadeButton variant="outline" size="lg">
            Deploy Fighter
          </ArcadeButton>
        </Link>
      </motion.div>
    </section>
  );
}
