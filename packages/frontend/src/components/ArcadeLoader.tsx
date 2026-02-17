"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface ArcadeLoaderProps {
  fullPage?: boolean;
  text?: string;
  className?: string;
}

export function ArcadeLoader({
  fullPage = false,
  text = "Loading",
  className,
}: ArcadeLoaderProps) {
  const content = (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className="h-3 w-3 rounded-sm bg-neon-orange"
            animate={{ opacity: [0.2, 1, 0.2] }}
            transition={{
              duration: 0.8,
              repeat: Infinity,
              delay: i * 0.12,
            }}
          />
        ))}
      </div>
      <span className="font-pixel text-[10px] text-muted-foreground">
        {text}
        <motion.span
          animate={{ opacity: [0, 1, 0] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        >
          ...
        </motion.span>
      </span>
    </div>
  );

  if (fullPage) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        {content}
      </div>
    );
  }

  return <div className="py-12 flex justify-center">{content}</div>;
}
