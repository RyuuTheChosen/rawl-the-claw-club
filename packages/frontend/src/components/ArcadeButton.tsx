"use client";

import { type ReactNode, type MouseEventHandler } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface ArcadeButtonProps {
  variant?: "primary" | "secondary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
  glow?: boolean;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: MouseEventHandler<HTMLButtonElement>;
}

const variantStyles = {
  primary:
    "bg-neon-orange text-background font-semibold hover:bg-neon-orange/90",
  secondary:
    "bg-secondary text-secondary-foreground font-medium hover:bg-secondary/80",
  outline:
    "border border-neon-orange/40 text-neon-orange bg-transparent hover:bg-neon-orange/10",
  ghost:
    "text-muted-foreground hover:text-foreground hover:bg-muted/50",
} as const;

const sizeStyles = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
} as const;

export function ArcadeButton({
  className,
  variant = "primary",
  size = "md",
  glow,
  children,
  disabled,
  type = "button",
  onClick,
}: ArcadeButtonProps) {
  return (
    <motion.button
      type={type}
      whileTap={disabled ? undefined : { scale: 0.95 }}
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:pointer-events-none disabled:opacity-50",
        variantStyles[variant],
        sizeStyles[size],
        glow && "shadow-neon-orange",
        className,
      )}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </motion.button>
  );
}
