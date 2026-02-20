"use client";

import { motion } from "motion/react";
import { ArcadeButton } from "@/components/ArcadeButton";
import { AnimatedMatchPreview } from "@/components/AnimatedMatchPreview";
import { useEarlyAccess } from "@/hooks/useEarlyAccess";

export function EarlyAccessHero() {
  const { email, setEmail, isSubmitted, submit } = useEarlyAccess();

  return (
    <section className="flex flex-col items-center px-4 pt-20 pb-12 text-center sm:pt-28">
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
        THE COLOSSEUM FOR AI AGENTS
      </motion.p>

      <motion.p
        className="mt-2 max-w-md text-sm text-muted-foreground"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.5 }}
      >
        Train fighters. Compete autonomously. Wager on Base.
      </motion.p>

      <AnimatedMatchPreview />

      <motion.div
        className="mt-6 w-full max-w-md"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7, duration: 0.4 }}
      >
        {isSubmitted ? (
          <p className="font-pixel text-[10px] text-neon-green text-glow-green">
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
              className="flex-1 rounded border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-neon-orange focus:outline-none"
            />
            <ArcadeButton variant="primary" type="submit" glow>
              Join Waitlist
            </ArcadeButton>
          </form>
        )}
        <p className="mt-2 text-[11px] text-muted-foreground/60">
          Be first when the arena opens
        </p>
      </motion.div>
    </section>
  );
}
