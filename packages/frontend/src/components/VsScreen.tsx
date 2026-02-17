"use client";

import { motion } from "motion/react";

interface VsScreenProps {
  fighterA?: string;
  fighterB?: string;
}

export function VsScreen({ fighterA = "P1", fighterB = "P2" }: VsScreenProps) {
  return (
    <div className="relative flex items-center justify-center gap-6 py-6">
      <motion.div
        initial={{ x: -80, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="text-right"
      >
        <span className="font-pixel text-lg text-neon-cyan text-glow-cyan sm:text-xl">
          {fighterA}
        </span>
      </motion.div>

      <motion.div
        initial={{ scale: 3, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.2, ease: [0.34, 1.56, 0.64, 1] }}
      >
        <span className="font-pixel text-2xl text-neon-orange text-glow-orange sm:text-3xl">
          VS
        </span>
      </motion.div>

      <motion.div
        initial={{ x: 80, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="text-left"
      >
        <span className="font-pixel text-lg text-neon-pink text-glow-pink sm:text-xl">
          {fighterB}
        </span>
      </motion.div>
    </div>
  );
}
