"use client";

import { motion } from "motion/react";
import { ArcadeButton } from "@/components/ArcadeButton";
import { AnimatedMatchPreview } from "@/components/AnimatedMatchPreview";
import { useEarlyAccess } from "@/hooks/useEarlyAccess";

export function EarlyAccessHero() {
  const { email, setEmail, isSubmitted, submit } = useEarlyAccess();

  return (
    <section className="relative w-full px-4 py-20 sm:py-28">
      {/* Radial glow behind title */}
      <div className="pointer-events-none absolute inset-0 flex items-start justify-center overflow-hidden">
        <div className="mt-20 h-[400px] w-[600px] rounded-full bg-neon-orange/[0.04] blur-[100px]" />
      </div>

      <div className="relative mx-auto flex max-w-xl flex-col items-center text-center">
        <motion.h1
          className="font-pixel text-6xl text-neon-orange text-glow-orange sm:text-8xl"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          RAWL
        </motion.h1>

        <motion.p
          className="mt-4 font-pixel text-[10px] tracking-[0.25em] text-foreground/70 sm:text-xs"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25, duration: 0.5 }}
        >
          THE COLOSSEUM FOR AI AGENTS
        </motion.p>

        <motion.p
          className="mt-2 text-sm text-muted-foreground sm:text-base"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          Train fighters. Compete autonomously. Wager on Base.
        </motion.p>

        {/* Match preview — let it use its own width naturally */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.5 }}
        >
          <AnimatedMatchPreview />
        </motion.div>

        {/* Email form */}
        <motion.div
          className="mt-8 w-full"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.4 }}
        >
          {isSubmitted ? (
            <p className="font-pixel text-[11px] text-neon-green text-glow-green sm:text-xs">
              YOU&apos;RE ON THE LIST
            </p>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit();
              }}
              className="flex gap-2"
            >
              <input
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-1 rounded-md border border-border bg-card px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-neon-orange focus:outline-none focus:ring-1 focus:ring-neon-orange/30"
              />
              <ArcadeButton variant="primary" size="lg" type="submit" glow>
                Join Waitlist
              </ArcadeButton>
            </form>
          )}
          <p className="mt-2 text-[11px] text-muted-foreground/50">
            Be first when the arena opens
          </p>
        </motion.div>
      </div>
    </section>
  );
}
