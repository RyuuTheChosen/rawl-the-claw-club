"use client";

import { Twitter, Github } from "lucide-react";
import { motion } from "motion/react";
import { ArcadeButton } from "@/components/ArcadeButton";
import { useEarlyAccess } from "@/hooks/useEarlyAccess";

const SOCIAL_LINKS = [
  { label: "Twitter", href: "https://x.com/RawlClawClub", icon: Twitter },
  { label: "GitHub", href: "https://github.com/RyuuTheChosen/rawl-the-claw-club", icon: Github },
] as const;

export function EarlyAccessCTA() {
  const { email, setEmail, isSubmitted, submit } = useEarlyAccess();

  return (
    <section className="mx-auto w-full max-w-xl px-4 py-14 sm:py-16 text-center">
      <motion.h2
        className="mb-6 font-pixel text-sm tracking-widest text-neon-orange text-glow-orange sm:text-base"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
      >
        GET EARLY ACCESS
      </motion.h2>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.2, duration: 0.4 }}
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
            className="mx-auto flex max-w-md gap-2"
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
      </motion.div>

      <motion.div
        className="mt-8 flex items-center justify-center gap-4"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.4, duration: 0.4 }}
      >
        {SOCIAL_LINKS.map((s) => (
          <a
            key={s.label}
            href={s.href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground transition-colors hover:text-foreground"
            aria-label={s.label}
          >
            <s.icon className="h-5 w-5" />
          </a>
        ))}
      </motion.div>
    </section>
  );
}
