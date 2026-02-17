"use client";

import { forwardRef, type ReactNode } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface ArcadeCardProps {
  children: ReactNode;
  className?: string;
  glowColor?: "orange" | "cyan" | "pink" | "green";
  hover?: boolean;
  onClick?: () => void;
}

const glowMap = {
  orange: "hover:shadow-neon-orange",
  cyan: "hover:shadow-neon-cyan",
  pink: "hover:shadow-neon-pink",
  green: "hover:shadow-neon-green",
} as const;

export const ArcadeCard = forwardRef<HTMLDivElement, ArcadeCardProps>(
  ({ children, className, glowColor = "orange", hover = true, onClick }, ref) => {
    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        whileHover={hover ? { scale: 1.01 } : undefined}
        onClick={onClick}
        className={cn(
          "arcade-border p-4",
          hover && glowMap[glowColor],
          onClick && "cursor-pointer",
          className,
        )}
      >
        {children}
      </motion.div>
    );
  },
);
ArcadeCard.displayName = "ArcadeCard";
