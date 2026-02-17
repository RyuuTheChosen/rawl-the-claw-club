"use client";

import { useEffect } from "react";
import { motion } from "motion/react";
import { ArcadeButton } from "@/components/ArcadeButton";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4">
      <motion.h1
        className="font-pixel text-2xl text-neon-red sm:text-4xl"
        initial={{ opacity: 0, scale: 1.5 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }}
      >
        GAME OVER
      </motion.h1>
      <motion.p
        className="max-w-md text-center text-sm text-muted-foreground"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        {error.message || "Something went wrong"}
      </motion.p>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <ArcadeButton onClick={reset} glow>
          CONTINUE?
        </ArcadeButton>
      </motion.div>
    </div>
  );
}
